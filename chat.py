import json
import re
import unicodedata

import chromadb
from openai import OpenAI

from config import (CHROMA_DIR, CHUNKS_DIR, GLOBAL_COLLECTION, HISTORY_LIMIT,
                    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, TOP_K)

_YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
_META_STOP = {"du", "de", "la", "le", "les", "des", "au", "aux", "sa", "spa", "sca",
              "and", "of", "ex", "et", "al", "groupe", "group", "bank", "maroc"}

STOP = {"est", "les", "des", "une", "dans", "pour", "avec", "entre", "quel", "quelle",
        "quels", "quelles", "comment", "donner", "donne", "fait", "sont", "avoir",
        "leur", "vers", "depuis", "plus", "maroc", "lorsque", "compte", "rapport"}

_COMPANY_INDEX: dict[str, str] | None = None

SYSTEM = (
    "Tu es un analyste financier expert specialise dans les rapports annuels des societes "
    "cotees a la Bourse de Casablanca, supervisees par l'AMMC (Autorite Marocaine du Marche "
    "des Capitaux). Tu as acces aux rapports annuels de toutes les entreprises listees a "
    "l'AMMC, couvrant de multiples secteurs (Banques, Assurances, Immobilier, Telecom, etc.) "
    "et plusieurs annees.\n"
    "Reponds en francais, de facon precise et concrete, uniquement a partir du contexte "
    "fourni. Precise toujours le nom de la societe et l'annee du rapport source. "
    "Recopie les montants exactement comme dans le contexte. "
    "Cite la page du rapport entre parentheses, ex. (ATTIJARIWAFA_BANK_2024, p.8). "
    "Si l'information n'est pas dans le contexte, dis-le clairement et ne l'invente pas.\n"
    "Mise en forme : utilise du markdown propre. "
    "Pour toute serie de donnees repetitives (actionnaires, bilans, provisions, "
    "participations, comparaisons entre entreprises...), presente-la dans un TABLEAU "
    "markdown au format :\n"
    "| Colonne 1 | Colonne 2 |\n"
    "| --- | --- |\n"
    "| valeur | valeur |\n"
    "Pour un petit nombre d'elements, utilise une liste a puces. "
    "Un court titre en gras ou en titre de niveau 3 peut introduire chaque partie. "
    "Chiffres et unites sont conserves tels quels (montants en milliers de dirhams)."
)

_corpus: list[dict] | None = None
_scraper_meta: dict | None = None


def _get_scraper_meta() -> dict:
    global _scraper_meta
    if _scraper_meta is None:
        from build_index import load_scraper_meta
        _scraper_meta = load_scraper_meta()
    return _scraper_meta


def _report_url(report: str) -> str:
    return _get_scraper_meta().get(report, {}).get("document_url", "")


def corpus() -> list[dict]:
    global _corpus
    if _corpus is None:
        meta_map = _get_scraper_meta()
        merged: list[dict] = []
        for f in sorted(CHUNKS_DIR.glob("*.json")):
            m = meta_map.get(f.stem, {})
            for c in json.loads(f.read_text(encoding="utf-8")):
                c.setdefault("report", f.stem)
                c.setdefault("company", m.get("company", ""))
                c.setdefault("company_normalized", m.get("company_normalized", f.stem))
                c.setdefault("year", m.get("year", ""))
                c.setdefault("sector", m.get("sector", ""))
                c.setdefault("url", m.get("document_url", ""))
                merged.append(c)
        _corpus = merged
    return _corpus


def invalidate() -> None:
    global _corpus
    _corpus = None


def _build_company_index() -> dict[str, str]:
    """Build alias→company_normalized map from scraper_meta."""
    meta_map = _get_scraper_meta()
    aliases: dict[str, str] = {}
    seen: set[str] = set()
    for stem, m in meta_map.items():
        norm = m.get("company_normalized", stem)
        if norm in seen:
            continue
        seen.add(norm)
        # Parts of the normalized slug
        for part in norm.split("_"):
            if len(part) >= 3 and part not in _META_STOP:
                aliases.setdefault(part, norm)
        # Parenthesized abbreviations in display name, e.g. "(BCP)"
        display = m.get("company", "")
        for abbr in re.findall(r'\(([A-Z]{2,})\)', display):
            aliases.setdefault(abbr.lower(), norm)
        # Words ≥4 from display name
        for word in re.split(r'[\s\-_()/]+', display):
            w = _fold(word)
            if len(w) >= 4 and w not in _META_STOP:
                aliases.setdefault(w, norm)
    return aliases


def _resolve_company(question: str, company: str | None) -> str | None:
    global _COMPANY_INDEX
    if company:
        return company
    if _COMPANY_INDEX is None:
        _COMPANY_INDEX = _build_company_index()
    folded = _fold(question)
    for token in re.findall(r'\b\w+\b', folded):
        if token in _COMPANY_INDEX:
            return _COMPANY_INDEX[token]
    return None


def load_store() -> chromadb.Collection | None:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        return client.get_collection(GLOBAL_COLLECTION)
    except Exception:
        return None


def warm_cache() -> None:
    try:
        collection = load_store()
        if collection is not None:
            collection.query(query_texts=["prechargement du modele"], n_results=1)
    except Exception:
        pass


def _expand(question: str) -> list[str]:
    q = question.lower()
    extra = []
    if "total" in q or "bilan" in q:
        extra.append("total actif passif resultat bilan notes chiffres consolide")
    if "action" in q:
        extra.append("resultat de base par action benefice titre nombre de titres")
    if any(k in q for k in ("decarbon", "décarbon", "engagements", "climat", "environnement", "esg")):
        extra.append("décarbonation engagements environnement entrepreneuriat derivés")
    # Re-issue query anchored to any year(s) mentioned to improve embedding recall
    years = _YEAR_RE.findall(question)
    if years:
        extra.append(question + " " + " ".join(years))
    return extra


def _fold(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()


def _keyword_hits(doc: str, keywords: list[tuple[str, float]]) -> float:
    folded = _fold(doc)
    return sum(w for kw, w in keywords if kw in folded)


def _keywords(question: str) -> list[tuple[str, float]]:
    tokens = sorted({_fold(t) for t in question.split() if len(t) >= 4 and _fold(t) not in STOP})
    return [(t, max(1.0, len(t) / 3.0)) for t in tokens[:5]]


def _build_where(
    rapport: str | None,
    company: str | None,
    year: str | list[str] | None,
    sector: str | None,
) -> dict | None:
    conditions = []
    if rapport:
        conditions.append({"report": {"$eq": rapport}})
    if company:
        conditions.append({"company_normalized": {"$eq": company}})
    if year:
        if isinstance(year, list) and len(year) > 1:
            conditions.append({"year": {"$in": [str(y) for y in year]}})
        elif isinstance(year, list):
            conditions.append({"year": {"$eq": str(year[0])}})
        else:
            conditions.append({"year": {"$eq": str(year)}})
    if sector:
        conditions.append({"sector": {"$eq": sector}})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def retrieve(
    collection: chromadb.Collection,
    question: str,
    k: int = TOP_K,
    rapport: str | None = None,
    company: str | None = None,
    year: str | list[str] | None = None,
    sector: str | None = None,
) -> list[dict]:
    queries = [question] + _expand(question)
    where = _build_where(rapport, company, year, sector)

    # Fetch vector results including docs+metadata in one call (avoids N individual gets)
    vector_rank: dict[str, float] = {}
    vector_docs: dict[str, dict] = {}
    for q in queries:
        try:
            res = collection.query(
                query_texts=[q],
                n_results=k,
                where=where,
                include=["metadatas", "documents", "distances"],
            )
            for ident, dist, meta, doc in zip(
                res["ids"][0], res["distances"][0],
                res["metadatas"][0], res["documents"][0],
            ):
                if ident not in vector_rank or dist < vector_rank[ident]:
                    vector_rank[ident] = dist
                    vector_docs[ident] = {
                        "text": doc,
                        "page": meta.get("page", "?"),
                        "report": meta.get("report", "?"),
                        "company": meta.get("company", "?"),
                        "year": meta.get("year", ""),
                        "sector": meta.get("sector", ""),
                        "url": _report_url(meta.get("report", "?")),
                    }
        except Exception:
            pass

    keywords = _keywords(question)
    # Normalize year filter for corpus scan
    _year_set: set[str] | None = None
    if year:
        _year_set = {str(y) for y in year} if isinstance(year, list) else {str(year)}

    boosted: list[tuple[float, float, dict]] = []
    if keywords:
        for c in corpus():
            if rapport and c.get("report") != rapport:
                continue
            if company and c.get("company_normalized") != company:
                continue
            if _year_set and str(c.get("year", "")) not in _year_set:
                continue
            if sector and c.get("sector", "") != sector:
                continue
            score = _keyword_hits(c["text"], keywords)
            if score > 0:
                ident = f"{c.get('report', '?')}::{c['id']}"
                boosted.append((score, vector_rank.get(ident, 1e9), c))

    boosted.sort(key=lambda x: (-x[0], x[1]))
    ranked: list[dict] = [c for _, _, c in boosted[:k]]

    seen = {f"{c.get('report', '?')}::{c['id']}" for c in ranked}
    for ident in sorted(vector_rank, key=lambda i: vector_rank[i]):
        if len(ranked) >= k:
            break
        if ident in seen:
            continue
        if ident in vector_docs:
            ranked.append(vector_docs[ident])
            seen.add(ident)

    return [
        {
            "text": c["text"],
            "page": c["page"],
            "report": c.get("report", "?"),
            "company": c.get("company", "?"),
            "year": c.get("year", ""),
            "sector": c.get("sector", ""),
            "url": c.get("url", _report_url(c.get("report", "?"))),
        }
        for c in ranked
    ]


def build_messages(question: str, hits: list[dict], history: list[dict]) -> list[dict]:
    context = "\n\n".join(
        f"[{h.get('company', h['report'])} {h.get('year', '')} · p.{h['page']}]\n{h['text'][:1500]}"
        for h in hits
    )
    user = (
        f"CONTEXTE (extraits du rapport financier) :\n{context}\n\n"
        f"QUESTION : {question}\n\nReponds uniquement avec ce contexte."
    )
    messages = [{"role": "system", "content": SYSTEM}]
    messages.extend(history[-HISTORY_LIMIT * 2 :])
    messages.append({"role": "user", "content": user})
    return messages


def answer(
    question: str,
    history: list[dict],
    rapport: str | None = None,
    company: str | None = None,
    year: str | None = None,
    sector: str | None = None,
) -> tuple[str, list[str]]:
    full, sources = "", []
    for chunk, src in answer_stream(question, history, rapport, company, year, sector):
        full += chunk
        if src:
            sources = src
    return full, sources


def _resolve_year(
    question: str,
    year: str | None,
) -> str | list[str] | None:
    """Return an effective year filter derived from the question if none was provided."""
    if year:
        return year
    found = _YEAR_RE.findall(question)
    if not found:
        return None
    unique = list(dict.fromkeys(found))  # preserve order, deduplicate
    return unique[0] if len(unique) == 1 else unique


def _sources(hits: list[dict]) -> list[dict]:
    by_page: dict[str, dict] = {}
    for h in hits:
        label = f"{h.get('company') or h.get('report', '?')}, p.{h['page']}"
        key = f"{h.get('report', '?')}::{h['page']}"
        by_page[key] = {
            "label": label,
            "page": h["page"],
            "report": h.get("report", "?"),
            "year": h.get("year", ""),
            "url": h.get("url", "") or _report_url(h.get("report", "?")),
        }
    return sorted(by_page.values(), key=lambda s: s["label"])


def answer_stream(
    question: str,
    history: list[dict],
    rapport: str | None = None,
    company: str | None = None,
    year: str | None = None,
    sector: str | None = None,
):
    collection = load_store()
    if collection is None:
        yield ("Index introuvable. Lancez d'abord : python ingest_scraped.py", [])
        return

    effective_year = _resolve_year(question, year)
    effective_company = _resolve_company(question, company)
    hits = retrieve(collection, question, rapport=rapport, company=effective_company, year=effective_year, sector=sector)
    if not hits:
        yield ("Aucun passage pertinent trouve dans les rapports.", [])
        return

    sources = _sources(hits)
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=180.0)
    messages = build_messages(question, hits, history)
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL, messages=messages, temperature=0.2, max_tokens=600
        )
        if not response.choices or not response.choices[0].message:
            yield ("L'API a retourne une reponse vide.", sources)
            return
        reply = response.choices[0].message.content or ""
        if not reply.strip():
            yield ("Le modèle n'a pas pu générer de réponse pour cette question.", sources)
            return
        yield (_dedup(reply), sources)
    except Exception as exc:
        yield (_offline_answer(hits, exc), sources)


def answer_stream_tokens(
    question: str,
    history: list[dict],
    rapport: str | None = None,
    company: str | None = None,
    year: str | None = None,
    sector: str | None = None,
):
    """Yields (token: str, sources: list | None). sources is None for intermediate tokens, set on final event."""
    collection = load_store()
    if collection is None:
        yield ("Index introuvable. Lancez d'abord : python ingest_scraped.py", [])
        return

    effective_year = _resolve_year(question, year)
    effective_company = _resolve_company(question, company)
    hits = retrieve(collection, question, rapport=rapport, company=effective_company, year=effective_year, sector=sector)
    if not hits:
        yield ("Aucun passage pertinent trouvé dans les rapports.", [])
        return

    sources = _sources(hits)
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=180.0)
    messages = build_messages(question, hits, history)
    try:
        stream = client.chat.completions.create(
            model=LLM_MODEL, messages=messages, temperature=0.2, max_tokens=600, stream=True
        )
        full = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                full += delta
                yield (delta, None)
        if not full.strip():
            yield ("Le modèle n'a pas pu générer de réponse pour cette question.", sources)
        else:
            yield ("", sources)
    except Exception as exc:
        yield (_offline_answer(hits, exc), sources)


def _dedup(text: str) -> str:
    half = len(text) // 2
    if half >= 20 and text[:half] and text == text[:half] * 2:
        return text[:half]
    return text


def _offline_answer(hits: list[dict], exc: Exception) -> str:
    lines = [
        f"{h.get('report', '?')} · p.{h['page']} - {h['text'][:500]}" for h in hits[:3]
    ]
    return (
        f"[API LLM injoignable : {type(exc).__name__}] Donnees repondues depuis l'index local.\n"
        + "\n".join(lines)
    )


if __name__ == "__main__":
    from main import run_chat

    run_chat()