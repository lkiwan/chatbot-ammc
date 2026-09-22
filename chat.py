import json
import unicodedata

import chromadb
from openai import OpenAI

from config import (CHROMA_DIR, CHUNKS_DIR, GLOBAL_COLLECTION, HISTORY_LIMIT,
                    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, TOP_K)

STOP = {"est", "les", "des", "une", "dans", "pour", "avec", "entre", "quel", "quelle",
        "quels", "quelles", "comment", "donner", "donne", "fait", "sont", "avoir",
        "leur", "vers", "depuis", "plus", "maroc", "lorsque", "compte", "rapport"}

SYSTEM = (
    "Tu es un analyste financier specialise. Reponds en francais, de facon precise et "
    "concrete, uniquement a partir du contexte fourni. "
    "Recopie les montants exactement comme dans le contexte, sans reformater ni reordonner "
    "les chiffres. Cite la page du rapport entre parentheses, ex. (p.8). "
    "Si l'information n'est pas dans le contexte, dis-le clairement et ne l'invente pas.\n"
    "Mise en forme : utilise du markdown propre, sans syntaxe brute apparente. "
    "Pour toute serie de donnees repetitives (actionnaires, bilans, provisions, "
    "participations...), presente-la dans un TABLEAU markdown au format :\n"
    "| Colonne 1 | Colonne 2 |\n"
    "| --- | --- |\n"
    "| valeur | valeur |\n"
    "Pour un petit nombre d'elements, utilise une liste a puces. "
    "Un court titre en gras ou en titre de niveau 3 peut introduire chaque partie. "
    "Chiffres et unites sont conserves tels quels (les montants en milliers de dirhams "
    "quand ils figurent ainsi dans le rapport)."
)

_corpus: list[dict] | None = None


def corpus() -> list[dict]:
    global _corpus
    if _corpus is None:
        merged: list[dict] = []
        for f in sorted(CHUNKS_DIR.glob("*.json")):
            for c in json.loads(f.read_text(encoding="utf-8")):
                c.setdefault("report", f.stem)
                merged.append(c)
        _corpus = merged
    return _corpus


def invalidate() -> None:
    global _corpus
    _corpus = None


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
    return extra


def _fold(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()


def _keyword_hits(doc: str, keywords: list[tuple[str, float]]) -> float:
    folded = _fold(doc)
    return sum(w for kw, w in keywords if kw in folded)


def _keywords(question: str) -> list[tuple[str, float]]:
    tokens = sorted({_fold(t) for t in question.split() if len(t) >= 4 and _fold(t) not in STOP})
    return [(t, max(1.0, len(t) / 3.0)) for t in tokens[:5]]


def retrieve(
    collection: chromadb.Collection,
    question: str,
    k: int = TOP_K,
    rapport: str | None = None,
) -> list[dict]:
    queries = [question] + _expand(question)

    vector_rank: dict[str, float] = {}
    for q in queries:
        res = collection.query(
            query_texts=[q],
            n_results=k,
            where={"report": rapport} if rapport else None,
        )
        for ident, dist in zip(res["ids"][0], res["distances"][0]):
            if ident not in vector_rank or dist < vector_rank[ident]:
                vector_rank[ident] = dist

    keywords = _keywords(question)
    boosted: list[tuple[float, float, dict]] = []
    for c in corpus():
        if rapport and c.get("report") != rapport:
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
        try:
            meta = collection.get(ids=[ident], include=["metadatas"])["metadatas"][0]
            doc = collection.get(ids=[ident], include=["documents"])["documents"][0]
        except Exception:
            continue
        ranked.append(
            {
                "text": doc,
                "page": meta.get("page", "?"),
                "report": meta.get("report", "?"),
            }
        )
        seen.add(ident)

    return [{"text": c["text"], "page": c["page"], "report": c.get("report", "?")} for c in ranked]


def build_messages(question: str, hits: list[dict], history: list[dict]) -> list[dict]:
    context = "\n\n".join(
        f"[Extrait p.{h['page']}]\n{h['text'][:2500]}" for h in hits
    )
    user = (
        f"CONTEXTE (extraits du rapport financier) :\n{context}\n\n"
        f"QUESTION : {question}\n\nReponds uniquement avec ce contexte."
    )
    messages = [{"role": "system", "content": SYSTEM}]
    messages.extend(history[-HISTORY_LIMIT * 2 :])
    messages.append({"role": "user", "content": user})
    return messages


def answer(question: str, history: list[dict], rapport: str | None = None) -> tuple[str, list[str]]:
    full, sources = "", []
    for chunk, src in answer_stream(question, history, rapport):
        full += chunk
        if src:
            sources = src
    return full, sources


def answer_stream(question: str, history: list[dict], rapport: str | None = None):
    collection = load_store()
    if collection is None:
        yield ("Index introuvable. Lancez d'abord : python main.py index", [])
        return

    hits = retrieve(collection, question, rapport=rapport)
    if not hits:
        yield ("Aucun passage pertinent trouve dans le rapport.", [])
        return

    sources = sorted({f"{h['report']} · p.{h['page']}" for h in hits})
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=180.0)
    messages = build_messages(question, hits, history)
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL, messages=messages, temperature=0.2
        )
        if not response.choices or not response.choices[0].message:
            yield ("L'API a retourne une reponse vide.", sources)
            return
        reply = response.choices[0].message.content or ""
        yield (_dedup(reply), sources)
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