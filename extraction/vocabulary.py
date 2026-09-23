"""
Financial vocabulary for Moroccan annual reports (French IFRS / PCM).

Maps raw metric labels (French/English variants) → normalized names.
"""
from __future__ import annotations

import re
import unicodedata

# ── Normalisation helpers ─────────────────────────────────────────────────────

def _fold(text: str) -> str:
    """Lowercase + strip accents + compress whitespace."""
    nfd = unicodedata.normalize("NFD", text)
    ascii_ = nfd.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_.lower()).strip()


# ── Metric alias table ────────────────────────────────────────────────────────
# Format: {normalized_name: [alias_patterns ...]}
# Each alias can be a substring that triggers the mapping.

METRIC_ALIASES: dict[str, list[str]] = {
    # ── Revenue ───────────────────────────────────────────────────────────
    "revenue": [
        "chiffre d'affaires", "chiffre d affaires", "ca net", "ca consolide",
        "revenus", "recettes", "produit net", "total produits",
        "ventes", "turnover", "revenue", "sales", "net revenue", "total revenue",
        "produits d exploitation", "produits operationnels",
    ],
    "net_banking_income": [
        "produit net bancaire", "pnb", "net banking income", "nbi",
        "produits bancaires nets",
    ],
    # ── Profitability ─────────────────────────────────────────────────────
    "gross_profit": [
        "marge brute", "resultat brut", "gross profit", "gross margin",
        "benefice brut",
    ],
    "operating_income": [
        "resultat d exploitation", "resultat operationnel", "resultat opérationnel",
        "rex", "resx", "ebit", "operating income", "operating profit",
        "benefice d exploitation", "profit d exploitation",
        "resultat des activites ordinaires",
    ],
    "ebitda": [
        "ebitda", "ebe", "excedent brut d exploitation",
        "resultat avant interets impots", "ebita", "operating ebitda",
    ],
    "finance_result": [
        "resultat financier", "resultat de financement", "charges financieres nettes",
        "produits financiers nets", "finance result", "financial income",
        "resultat des operations financieres",
    ],
    "profit_before_tax": [
        "resultat avant impots", "resultat avant impot",
        "benefice avant impots", "ebt", "profit before tax",
        "resultat courant avant impots", "rcai",
    ],
    "income_tax": [
        "impots sur le resultat", "impot sur les societes", "is",
        "charge d impot", "income tax", "tax expense",
        "impot sur le revenu",
    ],
    "net_income": [
        "resultat net", "benefice net", "profit net",
        "net income", "net profit", "profit for the year",
        "resultat net de l exercice", "resultat de l exercice",
        "resultat net consolide", "resultat net de la periode",
        "resultat net des activites poursuivies",
    ],
    "net_income_group_share": [
        "resultat net part du groupe", "rnpg", "resultat net pdg",
        "part du groupe", "net income group share",
        "resultat part groupe", "resultat attribuable aux actionnaires",
    ],
    "minority_interests": [
        "interets minoritaires", "part des minoritaires",
        "minority interests", "non-controlling interests",
        "part des tiers", "participations ne donnant pas le controle",
    ],
    # ── Balance Sheet: Assets ─────────────────────────────────────────────
    "total_assets": [
        "total actif", "total de l actif", "total des actifs",
        "total assets", "sum of assets", "actif total",
        "total bilan actif",
    ],
    "current_assets": [
        "actif circulant", "actif courant", "actifs courants",
        "current assets", "actif a court terme",
    ],
    "non_current_assets": [
        "actif immobilise", "actif non courant", "actifs non courants",
        "non-current assets", "fixed assets", "immobilisations",
        "actif a long terme",
    ],
    "cash": [
        "tresorerie", "disponibilites", "tresorerie et equivalents",
        "tresorerie et equivalents de tresorerie",
        "cash", "cash and cash equivalents", "cash equivalents",
        "liquidites", "valeurs disponibles",
    ],
    "receivables": [
        "creances clients", "creances commerciales", "creances",
        "accounts receivable", "trade receivables",
        "creances et comptes rattaches",
    ],
    "inventory": [
        "stocks", "inventaires", "inventory", "inventories",
        "marchandises", "produits finis",
    ],
    # ── Balance Sheet: Liabilities ────────────────────────────────────────
    "total_liabilities": [
        "total passif", "total du passif", "total des passifs",
        "total liabilities", "passif total",
        "total bilan passif",
    ],
    "current_liabilities": [
        "dettes a court terme", "passif courant", "passifs courants",
        "current liabilities", "dettes courantes",
    ],
    "non_current_liabilities": [
        "dettes a long terme", "passif non courant", "passifs non courants",
        "non-current liabilities", "dettes a moyen et long terme",
    ],
    "debt": [
        "dettes financieres", "emprunts", "dettes bancaires",
        "financial debt", "borrowings", "financial liabilities",
        "dettes financieres nettes", "credits bancaires",
        "emprunts et dettes assimilees",
    ],
    "equity": [
        "capitaux propres", "fonds propres", "capital propre",
        "equity", "shareholders equity", "net assets",
        "capitaux propres part du groupe", "total capitaux propres",
        "capitaux propres consolides",
    ],
    # ── Cash Flow ─────────────────────────────────────────────────────────
    "operating_cash_flow": [
        "flux de tresorerie d exploitation", "flux operationnels",
        "flux des activites operationnelles",
        "operating cash flow", "cash flow from operations",
        "capacite d autofinancement", "caf",
        "flux nets de tresorerie generes par l activite",
        "tresorerie generee par les operations",
    ],
    "investing_cash_flow": [
        "flux d investissement", "flux des activites d investissement",
        "investing activities", "cash flow from investing",
        "flux nets de tresorerie lies aux investissements",
    ],
    "financing_cash_flow": [
        "flux de financement", "flux des activites de financement",
        "financing activities", "cash flow from financing",
        "flux nets de tresorerie lies au financement",
    ],
    "capex": [
        "capex", "investissements", "acquisitions d immobilisations",
        "capital expenditures", "depenses d investissement",
        "acquisitions immobilisations corporelles",
    ],
    "free_cash_flow": [
        "free cash flow", "flux de tresorerie libre",
        "flux disponibles", "fcf",
    ],
    "net_change_in_cash": [
        "variation de tresorerie", "variation nette de tresorerie",
        "net change in cash", "cash variation",
        "augmentation diminution de tresorerie",
    ],
}

# Build a reverse lookup: folded_alias → normalized_name
_ALIAS_LOOKUP: dict[str, str] = {}
for _norm_name, _aliases in METRIC_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_LOOKUP[_fold(_alias)] = _norm_name

# ── Statement type classification ─────────────────────────────────────────────

_INCOME_KEYWORDS = {
    "chiffre d affaires", "resultat net", "resultat d exploitation",
    "marge brute", "ebitda", "ebe", "produit net bancaire", "pnb",
    "impot sur le resultat", "resultat financier", "benefice net",
    "produits d exploitation", "charges d exploitation",
}

_BALANCE_KEYWORDS = {
    "total actif", "total passif", "capitaux propres",
    "actif immobilise", "actif circulant",
    "dettes financieres", "emprunts",
    "actif non courant", "actif courant",
    "passif courant", "passif non courant",
}

_CASHFLOW_KEYWORDS = {
    "flux de tresorerie", "flux d exploitation",
    "flux d investissement", "flux de financement",
    "capacite d autofinancement", "caf",
    "variation de tresorerie",
}

_CATEGORY_MAP: dict[str, str] = {
    "revenue": "revenue",
    "net_banking_income": "revenue",
    "gross_profit": "profitability",
    "operating_income": "profitability",
    "ebitda": "profitability",
    "finance_result": "profitability",
    "profit_before_tax": "profitability",
    "income_tax": "profitability",
    "net_income": "profitability",
    "net_income_group_share": "profitability",
    "minority_interests": "profitability",
    "total_assets": "assets",
    "current_assets": "assets",
    "non_current_assets": "assets",
    "cash": "assets",
    "receivables": "assets",
    "inventory": "assets",
    "total_liabilities": "liabilities",
    "current_liabilities": "liabilities",
    "non_current_liabilities": "liabilities",
    "debt": "liabilities",
    "equity": "equity",
    "operating_cash_flow": "cash_flow",
    "investing_cash_flow": "cash_flow",
    "financing_cash_flow": "cash_flow",
    "capex": "cash_flow",
    "free_cash_flow": "cash_flow",
    "net_change_in_cash": "cash_flow",
}

_STATEMENT_MAP: dict[str, str] = {
    "revenue": "income_statement",
    "net_banking_income": "income_statement",
    "gross_profit": "income_statement",
    "operating_income": "income_statement",
    "ebitda": "income_statement",
    "finance_result": "income_statement",
    "profit_before_tax": "income_statement",
    "income_tax": "income_statement",
    "net_income": "income_statement",
    "net_income_group_share": "income_statement",
    "minority_interests": "income_statement",
    "total_assets": "balance_sheet",
    "current_assets": "balance_sheet",
    "non_current_assets": "balance_sheet",
    "cash": "balance_sheet",
    "receivables": "balance_sheet",
    "inventory": "balance_sheet",
    "total_liabilities": "balance_sheet",
    "current_liabilities": "balance_sheet",
    "non_current_liabilities": "balance_sheet",
    "debt": "balance_sheet",
    "equity": "balance_sheet",
    "operating_cash_flow": "cash_flow",
    "investing_cash_flow": "cash_flow",
    "financing_cash_flow": "cash_flow",
    "capex": "cash_flow",
    "free_cash_flow": "cash_flow",
    "net_change_in_cash": "cash_flow",
}


def normalize_metric_name(raw_label: str) -> str | None:
    """Map a raw metric label to its canonical name.

    Returns normalized name (e.g. 'net_income') or None if not recognized.
    Uses longest-match strategy: tests full string first, then substrings.
    """
    folded = _fold(raw_label)
    if not folded:
        return None

    # Exact match
    if folded in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[folded]

    # Substring match (longest alias wins)
    best: tuple[int, str] | None = None
    for alias, norm_name in _ALIAS_LOOKUP.items():
        if alias in folded:
            if best is None or len(alias) > best[0]:
                best = (len(alias), norm_name)

    if best:
        return best[1]

    return None


def classify_metric(normalized_name: str) -> tuple[str, str]:
    """Return (metric_category, statement_type) for a normalized metric name."""
    category = _CATEGORY_MAP.get(normalized_name, "other")
    statement = _STATEMENT_MAP.get(normalized_name, "other")
    return category, statement


def detect_statement_type(cell_texts: list[str]) -> str | None:
    """Infer which financial statement a table belongs to from its row labels."""
    folded_cells = {_fold(c) for c in cell_texts if c}

    income_hits = sum(1 for kw in _INCOME_KEYWORDS if any(kw in c for c in folded_cells))
    balance_hits = sum(1 for kw in _BALANCE_KEYWORDS if any(kw in c for c in folded_cells))
    cashflow_hits = sum(1 for kw in _CASHFLOW_KEYWORDS if any(kw in c for c in folded_cells))

    scores = {
        "income_statement": income_hits,
        "balance_sheet": balance_hits,
        "cash_flow": cashflow_hits,
    }

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] == 0:
        return None
    return best
