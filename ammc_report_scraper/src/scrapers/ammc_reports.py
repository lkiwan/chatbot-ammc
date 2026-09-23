"""Scrape individual document pages to extract the PDF download URL."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from src.config import SCRAPER
from src.parsers.report_parser import ReportRecord
from src.scrapers.base import BaseSession

logger = logging.getLogger(__name__)


class AMMCReportScraper:
    """
    Given a document page URL (e.g. /fr/espace-emetteurs/etats-financiers/xxx-rfa-2025),
    extract the direct PDF download URL.
    """

    BASE_URL = SCRAPER.base_url

    def __init__(self, session: BaseSession | None = None) -> None:
        self.session = session or BaseSession()

    def resolve_pdf_url(self, report: ReportRecord) -> str | None:
        """
        Fetch the document page and return the absolute PDF URL.
        Returns None if no PDF link is found.
        """
        soup = self.session.get_soup(report.source_url)
        if not soup:
            logger.warning("Could not fetch document page: %s", report.source_url)
            return None

        pdf_url = self._extract_pdf_link(soup)
        if pdf_url:
            logger.debug("PDF found for %s %s: %s", report.company_name, report.year, pdf_url)
        else:
            logger.warning(
                "No PDF link found on page: %s (company=%s year=%d)",
                report.source_url, report.company_name, report.year,
            )
        return pdf_url

    def _extract_pdf_link(self, soup: BeautifulSoup) -> str | None:
        """
        Find the PDF download link on the document page.

        Known patterns observed on AMMC:
        - <a href="/sites/default/files/AWB_RFA_2025.pdf">...</a>
        - Section labeled "Pièce jointe" or "Fichier" with the PDF link
        """
        # Strategy 1: direct href ending in .pdf
        pdf_links = soup.find_all("a", href=re.compile(r"\.pdf$", re.I))
        if pdf_links:
            href = pdf_links[0].get("href", "")
            return self._make_absolute(href)

        # Strategy 2: href containing /sites/default/files/
        file_links = soup.find_all("a", href=re.compile(r"/sites/default/files/", re.I))
        if file_links:
            href = file_links[0].get("href", "")
            return self._make_absolute(href)

        # Strategy 3: look for a "Pièce jointe" or attachment section
        attachment_section = soup.find(
            string=re.compile(r"pi.ce\s+jointe|attachment|fichier", re.I)
        )
        if attachment_section:
            parent = attachment_section.find_parent()
            if parent:
                link = parent.find_next("a", href=True)
                if link:
                    href = link.get("href", "")
                    if href:
                        return self._make_absolute(href)

        return None

    def _make_absolute(self, href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return self.BASE_URL + href
        return href

    def resolve_all(self, reports: list[ReportRecord]) -> list[ReportRecord]:
        """Resolve PDF URLs for a list of reports in-place."""
        for report in reports:
            if report.document_url:
                continue  # already resolved
            pdf_url = self.resolve_pdf_url(report)
            if pdf_url:
                report.document_url = pdf_url
        return reports
