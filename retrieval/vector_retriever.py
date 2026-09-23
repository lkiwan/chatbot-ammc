"""
Vector retriever: thin wrapper around ChromaDB / chat.py retrieve().

Delegates to the existing retrieve() function so we don't duplicate logic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VectorResult:
    chunks: list[dict]      # [{text, source, company, year, page, score}]
    query: str
    error: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return len(self.chunks) == 0

    def as_text(self, max_chunks: int = 5) -> str:
        """Format top N chunks as plain text for LLM context."""
        if self.is_empty:
            return "[No relevant document passages found.]"
        lines: list[str] = []
        for i, chunk in enumerate(self.chunks[:max_chunks], 1):
            company = chunk.get("company", "")
            year    = chunk.get("year", "")
            page    = chunk.get("page", "")
            source  = chunk.get("source", "")
            label   = f"[{company} {year} · p.{page}]" if company else f"[{source}]"
            lines.append(f"--- Passage {i} {label} ---")
            lines.append(chunk.get("text", ""))
        return "\n\n".join(lines)


class VectorRetriever:
    """Retrieve document passages from ChromaDB."""

    def retrieve(
        self,
        question: str,
        *,
        company: Optional[str] = None,
        year: Optional[int] = None,
        sector: Optional[str] = None,
        top_k: int = 8,
    ) -> VectorResult:
        """Run semantic search and return matching document chunks."""
        try:
            from chat import retrieve as _retrieve
            raw_results = _retrieve(
                question,
                company=company,
                year=str(year) if year else None,
                sector=sector,
                top_k=top_k,
            )
            chunks = self._normalize(raw_results)
            return VectorResult(chunks=chunks, query=question)

        except Exception as exc:
            logger.error("Vector retrieval failed: %s", exc)
            return VectorResult(chunks=[], query=question, error=str(exc))

    # ── Private ───────────────────────────────────────────────────────────────

    def _normalize(self, raw: list) -> list[dict]:
        """Normalize whatever retrieve() returns into uniform dicts."""
        results: list[dict] = []

        if not raw:
            return results

        # Handle list of dicts (already normalized form)
        if isinstance(raw[0], dict):
            for item in raw:
                results.append({
                    "text":    item.get("text", item.get("document", "")),
                    "source":  item.get("source", ""),
                    "company": item.get("company", ""),
                    "year":    item.get("year", ""),
                    "page":    item.get("page", ""),
                    "score":   item.get("score", item.get("distance", 0.0)),
                })
            return results

        # Handle list of strings
        for item in raw:
            results.append({
                "text":    str(item),
                "source":  "",
                "company": "",
                "year":    "",
                "page":    "",
                "score":   0.0,
            })
        return results
