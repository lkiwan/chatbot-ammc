"""Unit tests for normalization utilities."""
import pytest

from src.utils.normalization import normalize_company_name, normalize_sector, sanitize_filename


class TestNormalizeCompanyName:
    def test_same_name_different_case(self):
        a = normalize_company_name("Attijariwafa Bank")
        b = normalize_company_name("ATTIJARIWAFA BANK")
        assert a == b

    def test_hyphen_vs_space(self):
        a = normalize_company_name("Attijariwafa-Bank")
        b = normalize_company_name("Attijariwafa Bank")
        assert a == b

    def test_removes_accents(self):
        a = normalize_company_name("Crédit du Maroc")
        b = normalize_company_name("Credit du Maroc")
        assert a == b

    def test_strips_whitespace(self):
        assert normalize_company_name("  BMCE  ") == normalize_company_name("BMCE")

    def test_preserves_distinction(self):
        # Different companies should not collapse to the same normalized form
        a = normalize_company_name("CIH Bank")
        b = normalize_company_name("CDM Bank")
        assert a != b

    def test_legal_suffix_removal(self):
        a = normalize_company_name("TOTAL SA")
        b = normalize_company_name("TOTAL")
        assert a == b


class TestNormalizeSector:
    def test_lowercase(self):
        assert normalize_sector("BANQUES") == normalize_sector("Banques")

    def test_strips_accents(self):
        a = normalize_sector("Télécommunications")
        b = normalize_sector("Telecommunications")
        assert a == b

    def test_whitespace(self):
        assert normalize_sector("  Banques  ") == normalize_sector("Banques")


class TestSanitizeFilename:
    def test_removes_special_chars(self):
        result = sanitize_filename("Attijariwafa Bank / CDM")
        assert "/" not in result
        assert result  # not empty

    def test_uppercase(self):
        assert sanitize_filename("attijariwafa bank") == "ATTIJARIWAFA_BANK"

    def test_handles_accents(self):
        result = sanitize_filename("Crédit du Maroc")
        assert "é" not in result

    def test_no_leading_trailing_underscores(self):
        result = sanitize_filename("  test  ")
        assert not result.startswith("_")
        assert not result.endswith("_")
