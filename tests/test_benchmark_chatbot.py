"""
Chatbot benchmark: measures router accuracy, retrieval latency, and keyword scoring.

Run with:
    python -m pytest tests/benchmark_chatbot.py -v --tb=short
    python -m pytest tests/benchmark_chatbot.py -v -s --benchmark  # shows timing table
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import pytest

from retrieval.router import QueryType, classify_query


# ── Benchmark harness ────────────────────────────────────────────────────────

@dataclass
class BenchResult:
    name: str
    passed: int = 0
    failed: int = 0
    total_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        total = self.passed + self.failed
        return self.passed / total if total else 0.0

    @property
    def avg_ms(self) -> float:
        total = self.passed + self.failed
        return self.total_ms / total if total else 0.0


_results: list[BenchResult] = []


def _run_classification_bench(cases: list[tuple[str, QueryType | set]], name: str) -> BenchResult:
    result = BenchResult(name=name)
    for query, expected in cases:
        t0 = time.perf_counter()
        got = classify_query(query)
        result.total_ms += (time.perf_counter() - t0) * 1000
        if isinstance(expected, set):
            ok = got.query_type in expected
        else:
            ok = got.query_type == expected
        if ok:
            result.passed += 1
        else:
            result.failed += 1
            result.errors.append(f"  '{query[:60]}' → {got.query_type.value} (expected {expected})")
    _results.append(result)
    return result


# ── Router benchmark cases ────────────────────────────────────────────────────

SQL_CASES: list[tuple[str, QueryType]] = [
    ("Quel est le résultat net de Attijariwafa en 2022 ?", QueryType.SQL),
    ("Quel est l'EBITDA de OCP en 2021 ?", QueryType.SQL),
    ("Donner le chiffre d'affaires de Maroc Telecom pour 2023", QueryType.SQL),
    ("Quelle est la marge nette de CIH Bank en 2020 ?", QueryType.SQL),
    ("Résultat net consolidé de BCP en 2019", QueryType.SQL),
    ("Quels sont les actionnaires principaux de Alliances ?", QueryType.SQL),
    ("Quel est le total actif de BMCE Bank en 2022 ?", QueryType.SQL),
    ("Quel est le ROE de Wafa Assurance en 2021 ?", QueryType.SQL),
    ("Valeur du free cash flow de OCP en 2023", QueryType.SQL),
    ("Capitaux propres de Lydec en 2022", QueryType.SQL),
]

VECTOR_CASES: list[tuple[str, QueryType]] = [
    ("Quelle est la stratégie de développement de l'entreprise ?", QueryType.VECTOR),
    ("Quels sont les risques opérationnels mentionnés dans le rapport ?", QueryType.VECTOR),
    ("Comment fonctionne la gouvernance de l'entreprise ?", QueryType.VECTOR),
    ("Quels engagements RSE l'entreprise a-t-elle pris ?", QueryType.VECTOR),
    ("Décrivez les activités principales du groupe", QueryType.VECTOR),
    ("Quelles sont les perspectives pour l'exercice prochain ?", QueryType.VECTOR),
    ("Comment l'entreprise gère-t-elle ses ressources humaines ?", QueryType.VECTOR),
    ("Quelle est la politique de dividendes de la société ?", QueryType.VECTOR),
]

HYBRID_CASES: list[tuple[str, set]] = [
    ("Pourquoi le résultat net a-t-il augmenté en 2022 ?", {QueryType.HYBRID}),
    ("Quel est l'impact de la crise sur le chiffre d'affaires ?", {QueryType.HYBRID}),
    ("Quels facteurs expliquent la hausse du chiffre d'affaires ?", {QueryType.HYBRID}),
    ("Comment la performance financière reflète-t-elle la stratégie ?", {QueryType.HYBRID, QueryType.VECTOR}),
    ("Quelle est la relation entre les investissements et la rentabilité ?", {QueryType.HYBRID, QueryType.VECTOR}),
]

AMBIGUOUS_CASES: list[tuple[str, set]] = [
    ("Bonjour", {QueryType.VECTOR}),
    ("Parlez-moi de l'entreprise", {QueryType.VECTOR}),
    ("Compare les résultats 2020 et 2022", {QueryType.SQL, QueryType.HYBRID}),
    ("Évolution du CA sur 5 ans", {QueryType.SQL, QueryType.HYBRID}),
]


# ── Hint extraction cases ────────────────────────────────────────────────────

HINT_CASES = [
    ("Résultat net en 2021", {"year": 2021, "metric": "net_income"}),
    ("Chiffre d'affaires de 2020 à 2022", {"year": 2020}),
    ("EBITDA de Maroc Telecom en 2023", {"year": 2023, "metric": "ebitda"}),
    ("Capitaux propres en 2019", {"year": 2019}),
    ("Quel est le résultat ?", {"year": None}),
    ("Actionnaires de la société", {"metric": None}),
]


# ── Tests ────────────────────────────────────────────────────────────────────

class TestRouterBenchmark:
    def test_sql_routing_accuracy(self):
        r = _run_classification_bench(SQL_CASES, "SQL routing")
        assert r.accuracy >= 0.80, f"SQL accuracy {r.accuracy:.0%} < 80%\n" + "\n".join(r.errors)

    def test_vector_routing_accuracy(self):
        r = _run_classification_bench(VECTOR_CASES, "VECTOR routing")
        assert r.accuracy >= 0.75, f"VECTOR accuracy {r.accuracy:.0%} < 75%\n" + "\n".join(r.errors)

    def test_hybrid_routing_accuracy(self):
        r = _run_classification_bench(HYBRID_CASES, "HYBRID routing")
        assert r.accuracy >= 0.60, f"HYBRID accuracy {r.accuracy:.0%} < 60%\n" + "\n".join(r.errors)

    def test_ambiguous_routing_no_crash(self):
        r = _run_classification_bench(AMBIGUOUS_CASES, "AMBIGUOUS routing")
        # Just verify no crash and confidence is in [0,1]
        for query, _ in AMBIGUOUS_CASES:
            result = classify_query(query)
            assert 0.0 <= result.confidence <= 1.0, f"Invalid confidence for: {query}"

    def test_router_latency(self):
        queries = [q for q, _ in SQL_CASES + VECTOR_CASES + HYBRID_CASES]
        times = []
        for q in queries:
            t0 = time.perf_counter()
            classify_query(q)
            times.append((time.perf_counter() - t0) * 1000)
        avg = sum(times) / len(times)
        p99 = sorted(times)[int(len(times) * 0.99)]
        assert avg < 50, f"Router avg latency {avg:.1f}ms > 50ms"
        assert p99 < 200, f"Router p99 latency {p99:.1f}ms > 200ms"


class TestHintExtractionBenchmark:
    def test_year_extraction_accuracy(self):
        correct = 0
        total = sum(1 for _, expected in HINT_CASES if "year" in expected)
        for query, expected in HINT_CASES:
            if "year" not in expected:
                continue
            result = classify_query(query)
            if result.sql_hints.get("year") == expected["year"]:
                correct += 1
        accuracy = correct / total if total else 0
        assert accuracy >= 0.80, f"Year extraction accuracy {accuracy:.0%} < 80%"

    def test_metric_extraction_accuracy(self):
        correct = 0
        total = sum(1 for _, expected in HINT_CASES if "metric" in expected and expected["metric"] is not None)
        for query, expected in HINT_CASES:
            if "metric" not in expected or expected["metric"] is None:
                continue
            result = classify_query(query)
            if result.sql_hints.get("metric") == expected["metric"]:
                correct += 1
        accuracy = correct / total if total else 0
        assert accuracy >= 0.60, f"Metric extraction accuracy {accuracy:.0%} < 60%"

    def test_no_false_year_positives(self):
        no_year_queries = [
            "Quels sont les actionnaires ?",
            "Décrivez la stratégie",
            "Parlez de la gouvernance",
        ]
        for q in no_year_queries:
            result = classify_query(q)
            assert result.sql_hints.get("year") is None, f"False year positive for: {q}"


class TestConfidenceBenchmark:
    def test_sql_confidence_distribution(self):
        low_confidence = 0
        for query, _ in SQL_CASES:
            result = classify_query(query)
            if result.confidence < 0.5:
                low_confidence += 1
        # At most 30% of clear SQL queries should have low confidence
        assert low_confidence / len(SQL_CASES) <= 0.30, \
            f"{low_confidence}/{len(SQL_CASES)} SQL queries have confidence < 0.5"

    def test_vector_confidence_reasonable(self):
        for query, _ in VECTOR_CASES:
            result = classify_query(query)
            assert result.confidence > 0.0, f"Zero confidence for: {query}"


# ── Summary fixture ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="session")
def print_benchmark_summary():
    yield
    if not _results:
        return
    print("\n\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"{'Suite':<30} {'Acc':>6} {'Pass':>5} {'Fail':>5} {'Avg ms':>8}")
    print("-" * 60)
    for r in _results:
        total = r.passed + r.failed
        print(f"{r.name:<30} {r.accuracy:>6.0%} {r.passed:>5}/{total:<5} {r.avg_ms:>7.2f}")
    print("=" * 60)
