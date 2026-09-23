"""
Query router: classifies a question as SQL, VECTOR, or HYBRID.

Uses deterministic keyword patterns — no LLM call at routing stage.
"""
from __future__ import annotations

import enum
import re
import unicodedata
from dataclasses import dataclass


class QueryType(str, enum.Enum):
    SQL = "sql"         # structured financial fact
    VECTOR = "vector"   # qualitative / narrative
    HYBRID = "hybrid"   # needs both fact + explanation


# ── Keyword patterns ──────────────────────────────────────────────────────────

_SQL_KEYWORDS = {
    # Financial metrics
    "résultat net", "resultat net", "bénéfice net", "benefice net",
    "chiffre d'affaires", "chiffre d affaires", "ca",
    "total actif", "total bilan", "total passif",
    "capitaux propres", "fonds propres",
    "ebitda", "ebe", "pnb", "produit net bancaire",
    "résultat d'exploitation", "resultat d exploitation",
    "dettes financières", "dettes financieres",
    "trésorerie", "tresorerie",
    "actif total", "passif total",
    "résultat financier", "resultat financier",
    "marge brute", "résultat brut", "resultat brut",
    "free cash flow", "flux de trésorerie", "flux de tresorerie",
    # Comparative triggers
    "compare", "comparer", "comparaison", "évolution", "evolution",
    "variation", "croissance", "progression", "hausse", "baisse",
    "entre 20", "de 20", "en 20",
    # Query intents
    "quel est", "quelle est", "combien", "montant", "valeur",
    "chiffre", "données", "donnees", "statistique",
    # Ratios
    "roe", "roa", "roce", "marge", "ratio", "coefficient",
    # Shareholders
    "actionnaire", "participation", "capital", "structure",
}

_VECTOR_KEYWORDS = {
    "risque", "risques", "risk",
    "stratégie", "strategie", "strategy",
    "perspective", "perspectives", "outlook",
    "gouvernance", "governance",
    "responsabilité", "responsabilite", "rse",
    "développement durable", "developpement durable",
    "esg", "environnement", "environnemental",
    "management", "direction", "dirigeant",
    "marché", "marche", "market",
    "concurrence", "concurrent", "competition",
    "technologie", "innovation", "digital",
    "ressources humaines", "effectif", "emploi",
    "réglementaire", "reglementaire", "regulatory",
    "opinion", "note de l'auditeur", "commissaire",
    "mot du président", "message du directeur",
    "explique", "expliquer", "décrire", "decrire",
    "que dit", "que dit le rapport",
    "quels événements", "quels evenements",
}

_HYBRID_TRIGGERS = {
    "pourquoi", "comment expliquer", "raison",
    "facteur", "driver", "moteur",
    "augmenté", "augmente", "diminué", "diminue",
    "amélioré", "ameliore", "dégradé", "degrade",
    "impact", "effet", "conséquence", "consequence",
}

_YEAR_PATTERN = re.compile(r"\b20\d{2}\b|\b19\d{2}\b")
_COMPANY_VERBS = re.compile(
    r"\b(attijariwafa|bmce|bcp|cih|cosumar|managem|maroc telecom|iam|ocp)\b",
    re.I
)


def _fold(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    ascii_ = nfd.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_.lower()).strip()


@dataclass
class RouterResult:
    query_type: QueryType
    confidence: float
    reasoning: str
    sql_hints: dict[str, str | int | None]  # company, year, metric extracted from question


class QueryRouter:
    """Classify a question as SQL, VECTOR, or HYBRID."""

    def classify(self, question: str) -> RouterResult:
        folded = _fold(question)

        sql_hits = sum(1 for kw in _SQL_KEYWORDS if kw in folded)
        vector_hits = sum(1 for kw in _VECTOR_KEYWORDS if kw in folded)
        hybrid_hits = sum(1 for kw in _HYBRID_TRIGGERS if kw in folded)

        # Extract year(s) from question
        years = _YEAR_PATTERN.findall(question)
        year = int(years[0]) if years else None

        # Extract hints from question
        hints = self._extract_hints(question, year)

        # Routing decision
        if hybrid_hits >= 1 and (sql_hits >= 1 or vector_hits >= 1):
            return RouterResult(
                query_type=QueryType.HYBRID,
                confidence=0.8,
                reasoning=f"hybrid triggers ({hybrid_hits}) with sql ({sql_hits}) or vector ({vector_hits}) hits",
                sql_hints=hints,
            )

        if sql_hits >= 2 and sql_hits >= vector_hits:
            return RouterResult(
                query_type=QueryType.SQL,
                confidence=min(0.95, 0.5 + sql_hits * 0.1),
                reasoning=f"sql keywords matched: {sql_hits}",
                sql_hints=hints,
            )

        if vector_hits >= 2 and vector_hits > sql_hits:
            return RouterResult(
                query_type=QueryType.VECTOR,
                confidence=min(0.95, 0.5 + vector_hits * 0.1),
                reasoning=f"vector keywords matched: {vector_hits}",
                sql_hints=hints,
            )

        if sql_hits == 1 and vector_hits == 0:
            return RouterResult(
                query_type=QueryType.SQL,
                confidence=0.6,
                reasoning="single sql keyword match",
                sql_hints=hints,
            )

        # Default: vector (safer for ambiguous questions)
        return RouterResult(
            query_type=QueryType.VECTOR,
            confidence=0.5,
            reasoning="no strong signal — defaulting to vector",
            sql_hints=hints,
        )

    def _extract_hints(self, question: str, year: int | None) -> dict[str, str | int | None]:
        """Extract company name, year, and metric hints from question text."""
        folded = _fold(question)

        # Detect metric
        metric = None
        metric_map = {
            "résultat net": "net_income",
            "resultat net": "net_income",
            "bénéfice net": "net_income",
            "benefice net": "net_income",
            "chiffre d affaires": "revenue",
            "chiffre d'affaires": "revenue",
            "ebitda": "ebitda",
            "total actif": "total_assets",
            "total bilan": "total_assets",
            "capitaux propres": "equity",
            "fonds propres": "equity",
            "dettes financières": "debt",
            "dettes financieres": "debt",
            "trésorerie": "cash",
            "tresorerie": "cash",
            "pnb": "net_banking_income",
            "produit net bancaire": "net_banking_income",
        }
        for phrase, norm in metric_map.items():
            if phrase in folded:
                metric = norm
                break

        return {"year": year, "metric": metric}


# Convenience function
def classify_query(question: str) -> RouterResult:
    return QueryRouter().classify(question)
