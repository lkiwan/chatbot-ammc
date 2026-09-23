"""
Unit tests for extraction.normalizer — French number parsing and unit detection.
"""
import pytest
from extraction.normalizer import parse_number, detect_unit, parse_value_with_unit


class TestParseNumber:
    def test_simple_integer(self):
        assert parse_number("1245") == 1245.0

    def test_french_thousands_space(self):
        assert parse_number("1 245") == 1245.0

    def test_french_decimal_comma(self):
        assert parse_number("1 245,50") == 1245.50

    def test_english_decimal_dot(self):
        assert parse_number("1245.50") == 1245.50

    def test_negative_parentheses(self):
        assert parse_number("(125)") == -125.0

    def test_negative_parentheses_decimal(self):
        assert parse_number("(1 245,50)") == -1245.50

    def test_negative_sign(self):
        assert parse_number("-250") == -250.0

    def test_millions_abbreviation(self):
        # Raw number — no unit conversion here
        assert parse_number("1 245 678") == 1_245_678.0

    def test_empty_string(self):
        assert parse_number("") is None

    def test_dash(self):
        assert parse_number("-") is None
        assert parse_number("—") is None

    def test_not_a_number(self):
        assert parse_number("N/A") is None

    def test_zero(self):
        assert parse_number("0") == 0.0

    def test_large_number_dot_thousands(self):
        # "1.245.678" = French format with dot as thousands sep
        result = parse_number("1.245.678")
        assert result == 1_245_678.0


class TestDetectUnit:
    def test_mad(self):
        unit, mult = detect_unit("En MAD")
        assert unit == "MAD"
        assert mult == 1.0

    def test_kdh(self):
        unit, mult = detect_unit("En milliers de DH")
        assert unit == "KMAD"
        assert mult == 1_000.0

    def test_mdh(self):
        unit, mult = detect_unit("En millions de dirhams")
        assert unit == "MMAD"
        assert mult == 1_000_000.0

    def test_mmad(self):
        unit, mult = detect_unit("MMAD")
        assert unit == "MMAD"
        assert mult == 1_000_000.0

    def test_bmmad(self):
        unit, mult = detect_unit("en milliards de MAD")
        assert unit == "BMMAD"
        assert mult == 1_000_000_000.0

    def test_no_unit(self):
        unit, mult = detect_unit("Résultat net de l'exercice")
        assert unit is None
        assert mult == 1.0

    def test_case_insensitive(self):
        unit, _ = detect_unit("en kdh")
        assert unit == "KMAD"


class TestParseValueWithUnit:
    def test_plain_value_with_context_unit(self):
        pv = parse_value_with_unit("1 245 000", context_unit="MMAD")
        assert pv.value == 1_245_000.0
        assert pv.unit == "MMAD"

    def test_percentage(self):
        pv = parse_value_with_unit("12,5%")
        assert pv.value == pytest.approx(12.5)
        assert pv.is_percentage is True

    def test_negative_parentheses(self):
        pv = parse_value_with_unit("(500 000)")
        assert pv.value == -500_000.0
        assert pv.is_negative is True

    def test_none_for_empty(self):
        pv = parse_value_with_unit("")
        assert pv.value is None
