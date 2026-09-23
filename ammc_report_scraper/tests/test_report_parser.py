"""Unit tests for report parsing utilities."""
import pytest

from src.parsers.report_parser import (
    extract_year_from_text,
    extract_year_from_url,
    is_annual_report,
    make_report_id,
)


class TestIsAnnualReport:
    def test_rfa_slug_is_annual(self):
        assert is_annual_report("/fr/espace-emetteurs/etats-financiers/attijariwafa-bank-rfa-2025")

    def test_rfs_slug_is_not_annual(self):
        assert not is_annual_report("/fr/espace-emetteurs/etats-financiers/attijariwafa-bank-rfs-juin-2026")

    def test_text_rapport_annuel(self):
        assert is_annual_report("Rapport annuel")
        assert is_annual_report("Rapports annuels")
        assert is_annual_report("RAPPORT ANNUEL")

    def test_text_rapport_semestriel_excluded(self):
        assert not is_annual_report("Rapport semestriel")
        assert not is_annual_report("Rapports 1er semestre")
        assert not is_annual_report("Rapport du premier semestre")

    def test_annual_report_english(self):
        assert is_annual_report("Annual Report")

    def test_esg_excluded(self):
        assert not is_annual_report("Rapport ESG 2024")

    def test_rfa_keyword(self):
        assert is_annual_report("RFA 2025")

    def test_empty_string(self):
        assert not is_annual_report("")


class TestExtractYear:
    def test_from_url(self):
        assert extract_year_from_url("/etats-financiers/attijariwafa-bank-rfa-2025") == 2025
        assert extract_year_from_url("/etats-financiers/auto-hall-rfa-2022") == 2022

    def test_from_url_no_year(self):
        assert extract_year_from_url("/etats-financiers/no-year") is None

    def test_from_text(self):
        assert extract_year_from_text("Rapport annuel 2023") == 2023
        assert extract_year_from_text("2021 Annual Report") == 2021

    def test_from_text_no_year(self):
        assert extract_year_from_text("No year here") is None

    def test_year_range_valid(self):
        # Should match 2010-2029 pattern
        assert extract_year_from_url("/rfa-2019") == 2019
        assert extract_year_from_url("/rfa-2030") is None  # future beyond range


class TestLatest5Selection:
    """Test that sorting + selecting top 5 works correctly."""

    def _make_reports(self, years: list[int]) -> list:
        from src.parsers.report_parser import ReportRecord, DocumentType
        return [
            ReportRecord(
                company_id="1",
                company_name="TEST",
                company_name_normalized="test",
                sector="Banques",
                year=y,
                source_url=f"http://example.com/{y}",
            )
            for y in years
        ]

    def test_selects_5_most_recent(self):
        reports = self._make_reports([2019, 2020, 2021, 2022, 2023, 2024, 2025])
        reports.sort(key=lambda r: r.year, reverse=True)
        selected = reports[:5]
        assert [r.year for r in selected] == [2025, 2024, 2023, 2022, 2021]

    def test_fewer_than_5_available(self):
        reports = self._make_reports([2023, 2024])
        reports.sort(key=lambda r: r.year, reverse=True)
        selected = reports[:5]
        assert [r.year for r in selected] == [2024, 2023]

    def test_gap_years_included(self):
        # If 2024 is missing, 2020 should be selected as 5th
        reports = self._make_reports([2020, 2021, 2022, 2023, 2025])
        reports.sort(key=lambda r: r.year, reverse=True)
        selected = reports[:5]
        assert [r.year for r in selected] == [2025, 2023, 2022, 2021, 2020]


class TestMakeReportId:
    def test_format(self):
        assert make_report_id("2734", 2025) == "2734_2025"

    def test_uniqueness(self):
        assert make_report_id("2734", 2025) != make_report_id("2734", 2024)
        assert make_report_id("2734", 2025) != make_report_id("2735", 2025)
