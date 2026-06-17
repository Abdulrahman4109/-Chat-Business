import pytest
from app.heuristics import heuristic_extract
from app.models import FinancialData


class TestExtractionFallback:
    def test_heuristic_gives_reasonable_default(self):
        result = heuristic_extract(
            "I want a car worth 600,000. I have 200,000 savings. "
            "My monthly income is 10,000 salary, 4,000 bonuses, and 3,000 extra income. "
            "My expenses are 4,000 per month.",
            [600000, 200000, 10000, 4000, 3000, 4000],
        )
        assert result.goal_price == 600000.0
        assert result.current_savings == 200000.0
        assert result.monthly_income == 10000.0
        assert result.extra_income == 7000.0
        assert result.monthly_expenses == 4000.0

    def test_heuristic_handles_attached_arabic_numbers(self):
        result = heuristic_extract("عاوز اشتري عربية 9855وقب شهر 2000", [9855, 2000])
        assert result.goal_price == 9855.0
        assert result.monthly_income == 2000.0

    def test_heuristic_with_english_have_savings(self):
        result = heuristic_extract("I have 30000 saved for a car", [30000])
        assert result.current_savings == 30000.0

    def test_merge_prefers_verified_value(self):
        primary = FinancialData(current_savings=800000.0, all_numbers=[600000.0, 200000.0])
        fallback = FinancialData(current_savings=200000.0, all_numbers=[600000.0, 200000.0])
        from app.heuristics import merge_extractions
        merged = merge_extractions(primary, fallback)
        assert merged.current_savings == 200000.0
