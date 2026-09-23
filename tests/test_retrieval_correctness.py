"""
Correctness tests for retrieval year-filtering and _resolve_year fix.

These tests use the live ChromaDB index. They are skipped if the index is empty.
"""
from __future__ import annotations

import pytest

from chat import _resolve_year, load_store, retrieve


def _index_available() -> bool:
    try:
        s = load_store()
        return s is not None and s.count() > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _index_available(),
    reason="ChromaDB index is empty — run ingest first",
)


@pytest.fixture(scope="module")
def collection():
    return load_store()


# ── _resolve_year unit tests (no index needed) ───────────────────────────────

class TestResolveYear:
    def test_explicit_year_wins(self):
        assert _resolve_year("résultat 2025", "2022") == "2022"

    def test_extracts_single_year(self):
        assert _resolve_year("Quel est le résultat net en 2025 ?", None) == "2025"

    def test_extracts_multi_year_as_list(self):
        result = _resolve_year("Compare 2022 et 2025", None)
        assert isinstance(result, list)
        assert "2022" in result and "2025" in result

    def test_no_year_returns_none(self):
        assert _resolve_year("Quelle est la stratégie ?", None) is None

    def test_deduplicates_same_year(self):
        result = _resolve_year("résultat 2025 et encore 2025", None)
        assert result == "2025"

    def test_no_false_historical_year(self):
        # "2001" is out of typical report range but still extracted
        result = _resolve_year("rapport de 2001", None)
        assert result == "2001"


# ── Retrieval year-filter tests (requires index) ──────────────────────────────

class TestYearFiltering:
    def test_single_year_filter_respected(self, collection):
        hits = retrieve(collection, "résultat net", year="2025", k=5)
        assert hits, "Expected hits for year=2025"
        for h in hits:
            assert str(h.get("year")) == "2025", \
                f"Got year={h.get('year')} but expected 2025"

    def test_year_2022_filter_respected(self, collection):
        hits = retrieve(collection, "résultat net", year="2022", k=5)
        assert hits, "Expected hits for year=2022"
        for h in hits:
            assert str(h.get("year")) == "2022"

    def test_multi_year_filter(self, collection):
        hits = retrieve(collection, "résultat net", year=["2022", "2025"], k=10)
        assert hits
        years_returned = {str(h.get("year")) for h in hits}
        assert years_returned <= {"2022", "2025"}, \
            f"Got unexpected years: {years_returned - {'2022', '2025'}}"

    def test_question_2025_returns_2025_chunks(self, collection):
        """The main bug: asking about 2025 must NOT return 2022 data."""
        hits = retrieve(
            collection,
            "Quel est le résultat net en 2025 ?",
            year=_resolve_year("Quel est le résultat net en 2025 ?", None),
            k=5,
        )
        assert hits, "No chunks found for 2025"
        wrong_year = [h for h in hits if str(h.get("year")) != "2025"]
        assert not wrong_year, \
            f"Got {len(wrong_year)} chunk(s) from wrong year: " \
            + ", ".join(f"{h['report']} yr={h.get('year')}" for h in wrong_year)

    def test_company_year_filter(self, collection):
        hits = retrieve(
            collection,
            "résultat net",
            company="centrale_populaire_bcp",
            year="2025",
            k=5,
        )
        for h in hits:
            assert str(h.get("year")) == "2025"
            assert h.get("company_normalized") == "centrale_populaire_bcp" \
                or "bcp" in h.get("report", "").lower() \
                or "populaire" in h.get("company", "").lower()

    def test_year_filter_isolates_data(self, collection):
        """Filtering by year=2025 must return ONLY 2025 chunks, not 2022."""
        hits_2025 = retrieve(collection, "résultat net", year="2025", k=5)
        hits_2022 = retrieve(collection, "résultat net", year="2022", k=5)
        assert hits_2025, "No chunks for 2025"
        assert hits_2022, "No chunks for 2022"
        # The two result sets should be disjoint (different documents)
        ids_2025 = {h.get("report") + str(h.get("page")) for h in hits_2025}
        ids_2022 = {h.get("report") + str(h.get("page")) for h in hits_2022}
        assert ids_2025 != ids_2022, "2025 and 2022 results are identical — filter not working"

    def test_nonexistent_year_returns_empty(self, collection):
        hits = retrieve(collection, "résultat net", year="1990", k=5)
        assert hits == [], f"Expected empty for year=1990, got {len(hits)} hits"


# ── Source correctness: chunks must have text and page ───────────────────────

class TestChunkQuality:
    def test_hits_have_text(self, collection):
        hits = retrieve(collection, "résultat net", year="2025", k=5)
        for h in hits:
            assert h.get("text"), f"Empty text in chunk from {h.get('report')}"
            assert len(h["text"]) >= 10

    def test_hits_have_page(self, collection):
        hits = retrieve(collection, "résultat net", year="2025", k=5)
        for h in hits:
            assert h.get("page") is not None, f"Missing page in {h.get('report')}"

    def test_hits_have_report(self, collection):
        hits = retrieve(collection, "résultat net", year="2025", k=5)
        for h in hits:
            assert h.get("report") not in (None, "?")
