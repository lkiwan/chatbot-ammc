"""Scrape a single company's emitter page to extract annual report links."""
from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from src.config import SCRAPER, ENDPOINTS, REPORTS
from src.parsers.report_parser import (
    DocumentType,
    ReportRecord,
    extract_year_from_url,
    extract_year_from_text,
    is_annual_report,
    make_report_id,
)
from src.parsers.emitter_parser import EmitterRecord
from src.scrapers.base import BaseSession
from src.utils.normalization import normalize_company_name

logger = logging.getLogger(__name__)


class AMMCCompanyScraper:
    """
    Scrapes an individual company's AMMC emitter page to find annual reports.

    The emitter page at /fr/espace-emetteurs/liste-des-emetteurs/{node_id}
    lists all financial documents including annual reports with direct links
    to their document pages.
    """

    BASE_URL = SCRAPER.base_url

    def __init__(self, session: BaseSession | None = None) -> None:
        self.session = session or BaseSession()

    def get_annual_reports(self, emitter: EmitterRecord) -> list[ReportRecord]:
        """
        Fetch the company's emitter page and return all annual report entries.
        Returns an empty list on failure.
        """
        soup = self.session.get_soup(emitter.ammc_url)
        if not soup:
            logger.warning("Could not fetch emitter page for %s", emitter.company_name)
            return []

        reports = self._extract_document_links(soup, emitter)
        annual = [r for r in reports if r.document_type == DocumentType.ANNUAL_REPORT]

        logger.info(
            "%s: found %d documents, %d annual reports",
            emitter.company_name, len(reports), len(annual),
        )
        return annual

    def _extract_document_links(
        self, soup: BeautifulSoup, emitter: EmitterRecord
    ) -> list[ReportRecord]:
        """
        Extract all financial document links from the emitter page.

        The page lists documents in a section with links to:
        /fr/espace-emetteurs/etats-financiers/{slug}
        """
        records: list[ReportRecord] = []
        seen_urls: set[str] = set()

        # Strategy 1: Find all links matching the etats-financiers pattern
        doc_links = soup.find_all(
            "a", href=re.compile(r"/etats-financiers/", re.I)
        )

        for link in doc_links:
            href: str = link.get("href", "")
            if not href:
                continue

            # Make absolute URL
            if href.startswith("/"):
                full_url = self.BASE_URL + href
            else:
                full_url = href

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            link_text = link.get_text(strip=True)
            year = extract_year_from_url(href) or extract_year_from_text(link_text)
            if not year:
                # Try to get year from parent text
                parent = link.parent
                if parent:
                    parent_text = parent.get_text()
                    year = extract_year_from_text(parent_text)

            if not year:
                logger.debug("Could not extract year from: %s / %s", href, link_text)
                continue

            # Determine document type from URL slug and link text
            combined = href + " " + link_text
            if is_annual_report(combined):
                doc_type = DocumentType.ANNUAL_REPORT
            elif REPORTS.semester_slug_marker in href.lower() or "semestr" in combined.lower():
                doc_type = DocumentType.SEMESTER_REPORT
            else:
                doc_type = DocumentType.OTHER

            report = ReportRecord(
                report_id=make_report_id(emitter.company_id, year),
                company_id=emitter.company_id,
                company_name=emitter.company_name_original,
                company_name_normalized=emitter.company_name_normalized,
                sector=emitter.sector,
                year=year,
                document_type=doc_type,
                title=link_text or f"{emitter.company_name} - {year}",
                source_url=full_url,
            )
            records.append(report)

        # Strategy 2: Fallback – find a table/list section labeled "Etats financiers"
        if not records:
            records = self._fallback_extract(soup, emitter)

        return records

    def _fallback_extract(
        self, soup: BeautifulSoup, emitter: EmitterRecord
    ) -> list[ReportRecord]:
        """Fallback: search broader link patterns on the page."""
        records: list[ReportRecord] = []
        # Match any link containing the company slug or year pattern
        all_links = soup.find_all("a", href=True)
        for link in all_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if "etats-financiers" not in href.lower():
                continue
            combined = href + " " + text
            year = extract_year_from_url(href) or extract_year_from_text(text)
            if not year:
                continue
            if is_annual_report(combined):
                full_url = (self.BASE_URL + href) if href.startswith("/") else href
                records.append(ReportRecord(
                    report_id=make_report_id(emitter.company_id, year),
                    company_id=emitter.company_id,
                    company_name=emitter.company_name_original,
                    company_name_normalized=emitter.company_name_normalized,
                    sector=emitter.sector,
                    year=year,
                    document_type=DocumentType.ANNUAL_REPORT,
                    title=text or f"{emitter.company_name} - RFA {year}",
                    source_url=full_url,
                ))
        return records
