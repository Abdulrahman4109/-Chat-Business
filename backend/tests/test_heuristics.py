import pytest
from app.heuristics import (
    normalize_number,
    normalize_text,
    extract_number_mentions,
    heuristic_extract,
    merge_extractions,
    apply_intelligent_defaults,
)
from app.models import FinancialData


class TestNormalizeNumber:
    def test_simple(self):
        assert normalize_number("5000") == 5000.0

    def test_with_k(self):
        assert normalize_number("5k") == 5000.0

    def test_with_m(self):
        assert normalize_number("2m") == 2000000.0

    def test_with_currency(self):
        assert normalize_number("$40000") == 40000.0

    def test_with_arabic_digit(self):
        assert normalize_number("٥٠٠٠") == 5000.0

    def test_invalid(self):
        assert normalize_number("abc") is None


class TestNormalizeText:
    def test_arabic_to_english(self):
        assert normalize_text("١٢٣") == "123"

    def test_mixed(self):
        assert normalize_text("عندي ٥٠٠٠") == "عندي 5000"


class TestExtractNumberMentions:
    def test_basic(self):
        mentions = extract_number_mentions("I have 5000")
        assert len(mentions) >= 1
        assert mentions[0].value == 5000.0

    def test_multiple(self):
        mentions = extract_number_mentions("earn 6500, spend 4200")
        values = [m.value for m in mentions]
        assert 6500.0 in values
        assert 4200.0 in values


class TestHeuristicExtract:
    def test_income_and_expenses(self):
        result = heuristic_extract("I earn 6500 monthly and spend 4200", [6500, 4200])
        assert result.monthly_income == 6500.0
        assert result.monthly_expenses == 4200.0

    def test_goal_with_savings(self):
        result = heuristic_extract("I want to buy a 40000 car. I have 8000 saved.", [40000, 8000])
        assert result.goal_price == 40000.0
        assert result.current_savings == 8000.0

    def test_arabic_input(self):
        result = heuristic_extract("عايز أشتري عربية ب 40000 و معايا 8000", [40000, 8000])
        assert result.goal_price == 40000.0
        assert result.current_savings == 8000.0

    def test_empty_text(self):
        result = heuristic_extract("", [])
        assert result.monthly_expenses == 0
        assert result.current_savings == 0
        assert result.extra_income == 0


class TestApplyIntelligentDefaults:
    def test_none_values_normalized(self):
        data = FinancialData()
        result = apply_intelligent_defaults(data)
        assert result.current_savings == 0
        assert result.extra_income == 0
        assert result.monthly_expenses == 0

    def test_goal_creates_goals_list(self):
        data = FinancialData(goal_price=50000.0)
        result = apply_intelligent_defaults(data)
        assert len(result.goals) == 1
        assert result.goals[0]["goal_price"] == 50000.0


class TestMergeExtractions:
    def test_primary_takes_precedence(self):
        primary = FinancialData(goal_price=50000.0, monthly_income=7000.0)
        fallback = FinancialData(goal_price=40000.0, monthly_income=6000.0)
        merged = merge_extractions(primary, fallback)
        assert merged.goal_price == 50000.0
        assert merged.monthly_income == 7000.0

    def test_fallback_fills_nulls(self):
        primary = FinancialData(monthly_income=7000.0)
        fallback = FinancialData(monthly_expenses=3000.0)
        merged = merge_extractions(primary, fallback)
        assert merged.monthly_income == 7000.0
        assert merged.monthly_expenses == 3000.0