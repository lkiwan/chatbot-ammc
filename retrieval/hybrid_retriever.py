"""
Hybrid retriever: combines SQL (structured facts) + vector (narrative context).

Flow:
  1. Router classifies the question.
  2. SQL branch fetches precise financial numbers.
  3. Vector branch fetches supporting document passages.
  4. Results are merged into a single context string for the LLM.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from retrieval.router import QueryRouter, QueryType, RouterResult
from retrieval.sql_retriever import SQLResult, SQLRetriever
from retrieval.vector_retriever import VectorResult, VectorRetriever

logger = logging.getLogger(__name__)


@dataclass
class HybridResult:
    query_type: QueryType
    router_result: RouterResult
    sql_result: Optional[SQLResult] = None
    vector_result: Optional[VectorResult] = None
    error: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        sql_empty   = self.sql_result is None or self.sql_result.is_empty
        vec_empty   = self.vector_result is None or self.vector_result.is_empty
        return sql_empty and vec_empty

    def build_context(self, max_vector_chunks: int = 5) -> str:
        """Build a combined context string to inject into the LLM prompt."""
        sections: list[str] = []

        if self.sql_result and not self.sql_result.is_empty:
            sections.append("## Données financières structurées (PostgreSQL)\n" + self.sql_result.as_text())

        if self.sql_result and self.sql_result.error:
            sections.append(f"[SQL error: {self.sql_result.error}]")

        if self.vector_result and not self.vector_result.is_empty:
            sections.append("## Passages du rapport annuel\n" + self.vector_result.as_text(max_vector_chunks))

        if self.vector_result and self.vector_result.error:
            sections.append(f"[Vector search error: {self.vector_result.error}]")

        if not sections:
            return "[Aucune donnée disponible pour cette question.]"

        return "\n\n".join(sections)


class HybridRetriever:
    """Orchestrate SQL + vector retrieval based on query classification."""

    def __init__(self) -> None:
        self._router  = QueryRouter()
        self._sql     = SQLRetriever()
        self._vector  = VectorRetriever()

    def retrieve(
        self,
        question: str,
        *,
        company: Optional[str] = None,
        year: Optional[int] = None,
        sector: Optional[str] = None,
        top_k: int = 8,
    ) -> HybridResult:
        """Route and retrieve context for the given question."""
        route = self._router.classify(question)
        logger.info(
            "Route: %s (conf=%.2f) | company=%s year=%s | reason: %s",
            route.query_type, route.confidence, company, year, route.reasoning,
        )

        # Merge year from filter param with year hinted from question text
        effective_year = year or route.sql_hints.get("year")
        effective_company = company  # explicit filter always wins
        effective_metric  = route.sql_hints.get("metric")

        sql_result: Optional[SQLResult] = None
        vec_result: Optional[VectorResult] = None

        if route.query_type in (QueryType.SQL, QueryType.HYBRID):
            sql_result = self._run_sql(
                question,
                company=effective_company,
                year=effective_year,
                metric=effective_metric,
            )

        if route.query_type in (QueryType.VECTOR, QueryType.HYBRID):
            vec_result = self._vector.retrieve(
                question,
                company=effective_company,
                year=effective_year,
                sector=sector,
                top_k=top_k,
            )

        return HybridResult(
            query_type=route.query_type,
            router_result=route,
            sql_result=sql_result,
            vector_result=vec_result,
        )

    # ── SQL dispatch ──────────────────────────────────────────────────────────

    def _run_sql(
        self,
        question: str,
        company: Optional[str],
        year: Optional[int],
        metric: Optional[str],
    ) -> SQLResult:
        """Dispatch to the most appropriate SQL query."""

        # No company → can't run useful metric query; fall back gracefully
        if not company:
            logger.debug("SQL: no company filter — skipping metric query")
            return SQLResult(rows=[], query_description="(no company specified for SQL)")

        if metric and year:
            return self._sql.get_metric(company, metric, year)

        if metric:
            return self._sql.compare_metric_across_years(company, metric)

        if year:
            # Return the income statement as the most useful summary
            result = self._sql.get_income_statement(company, year)
            if result.is_empty:
                result = self._sql.get_metric(company, "net_income", year)
            return result

        # Fallback: available years summary
        return self._sql.get_company_available_years(company)
