"""Scrape the AMMC emitters list to get all companies with sectors."""
from __future__ import annotations

import logging
import re
from typing import Iterator

from bs4 import BeautifulSoup, Tag

from src.config import SCRAPER, ENDPOINTS
from src.parsers.emitter_parser import EmitterRecord, extract_node_id
from src.scrapers.base import BaseSession
from src.utils.normalization import normalize_company_name, normalize_sector

logger = logging.getLogger(__name__)


class AMMCEmitterScraper:
    """Scrapes /fr/espace-emetteurs/liste-des-emetteurs across all pages."""

    BASE_URL = SCRAPER.base_url
    LIST_PATH = ENDPOINTS.emitters_list

    def __init__(self, session: BaseSession | None = None) -> None:
        self.session = session or BaseSession()

    def _list_url(self, page: int) -> str:
        return f"{self.BASE_URL}{self.LIST_PATH}?page={page}"

    def _parse_page(self, soup: BeautifulSoup) -> list[EmitterRecord]:
        records: list[EmitterRecord] = []

        # The emitters list is an HTML table; find all rows with a link
        # that matches the pattern /fr/espace-emetteurs/liste-des-emetteurs/{id}
        links = soup.find_all("a", href=re.compile(r"/liste-des-emetteurs/\d+"))
        seen_ids: set[str] = set()

        for link in links:
            href: str = link.get("href", "")
            node_id = extract_node_id(href)
            if not node_id or node_id in seen_ids:
                continue
            seen_ids.add(node_id)

            company_name = link.get_text(strip=True)
            if not company_name:
                continue

            # Sector: look in the same table row <tr>
            sector = self._extract_sector_from_row(link)

            ammc_url = f"{self.BASE_URL}{href}"

            records.append(EmitterRecord(
                company_id=node_id,
                company_name=company_name,
                company_name_original=company_name,
                company_name_normalized=normalize_company_name(company_name),
                sector=sector,
                sector_normalized=normalize_sector(sector),
                ammc_url=ammc_url,
            ))

        return records

    @staticmethod
    def _extract_sector_from_row(link_tag: Tag) -> str:
        """
        Walk up to <tr> and grab the sector column.
        Actual table layout observed: [empty | company name | sector | date]
        """
        tr = link_tag.find_parent("tr")
        if not tr:
            return ""

        tds = tr.find_all("td")

        # Primary: sector is in td[2] (4-column layout: icon | name | sector | date)
        if len(tds) >= 3:
            sector_text = tds[2].get_text(strip=True)
            if sector_text and sector_text != link_tag.get_text(strip=True):
                return sector_text

        # Fallback for 3-column layout (name | sector | date)
        if len(tds) >= 2:
            sector_text = tds[1].get_text(strip=True)
            if sector_text and sector_text != link_tag.get_text(strip=True):
                return sector_text

        # Last resort: <em> tag
        em = tr.find("em")
        if em:
            return em.get_text(strip=True)

        return ""

    def _get_last_page(self, soup: BeautifulSoup) -> int:
        """Find the last page number from pagination."""
        # Look for "Dernière page" or the highest page link
        last_link = soup.find("a", title=re.compile(r"derni.re|last", re.I))
        if last_link:
            href = last_link.get("href", "")
            m = re.search(r"[?&]page=(\d+)", href)
            if m:
                return int(m.group(1))

        # Fallback: find all page links and take max
        page_links = soup.find_all("a", href=re.compile(r"[?&]page=\d+"))
        pages = []
        for a in page_links:
            m = re.search(r"[?&]page=(\d+)", a.get("href", ""))
            if m:
                pages.append(int(m.group(1)))
        return max(pages) if pages else 0

    def scrape_all(
        self,
        sector_filter: str | None = None,
        company_filter: str | None = None,
    ) -> list[EmitterRecord]:
        """Scrape all pages of the emitters list."""
        logger.info("Starting emitters list scrape")

        # Fetch page 0 to discover total pages
        url0 = self._list_url(0)
        soup0 = self.session.get_soup(url0)
        if not soup0:
            logger.error("Failed to fetch emitters list page 0")
            return []

        last_page = self._get_last_page(soup0)
        logger.info("Emitters list: %d pages total (0 to %d)", last_page + 1, last_page)

        all_records: list[EmitterRecord] = []

        # Parse page 0
        records = self._parse_page(soup0)
        all_records.extend(records)
        logger.info("Page 0: %d emitters found", len(records))

        # Fetch remaining pages
        for page in range(1, last_page + 1):
            url = self._list_url(page)
            logger.debug("Fetching emitters page %d: %s", page, url)
            soup = self.session.get_soup(url)
            if not soup:
                logger.warning("Failed to fetch emitters page %d", page)
                continue
            records = self._parse_page(soup)
            all_records.extend(records)
            logger.debug("Page %d: %d emitters", page, len(records))

        logger.info("Emitters list scrape complete: %d total", len(all_records))

        # Apply filters
        if sector_filter:
            sector_lower = sector_filter.lower()
            all_records = [r for r in all_records if sector_lower in r.sector.lower()]
            logger.info("After sector filter '%s': %d companies", sector_filter, len(all_records))

        if company_filter:
            company_lower = company_filter.lower()
            all_records = [r for r in all_records if company_lower in r.company_name.lower()]
            logger.info("After company filter '%s': %d companies", company_filter, len(all_records))

        return all_records
