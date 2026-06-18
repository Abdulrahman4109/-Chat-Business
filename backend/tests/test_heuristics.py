import pytest
from app.heuristics import (
    normalize_number,
    normalize_text,
    extract_number_mentions,
    heuristic_extract,
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
        assert 6500.0 in result.all_numbers
        assert 4200.0 in result.all_numbers

    def test_goal_with_savings(self):
        result = heuristic_extract("I want to buy a 40000 car. I have 8000 saved.", [40000, 8000])
        assert 40000.0 in result.all_numbers
        assert 8000.0 in result.all_numbers

    def test_arabic_input(self):
        result = heuristic_extract("عايز أشتري عربية ب 40000 و معايا 8000", [40000, 8000])
        assert 40000.0 in result.all_numbers
        assert 8000.0 in result.all_numbers

    def test_empty_text(self):
        result = heuristic_extract("", [])
        assert result.all_numbers == []
        assert result.monthly_expenses == 0
        assert result.current_savings == 0
        assert result.extra_income == 0

    def test_english_full_example(self):
        result = heuristic_extract(
            "I want a car worth 600,000. I have 200,000 savings. "
            "My monthly income is 10,000 salary, 4,000 bonuses, and 3,000 extra income. "
            "My expenses are 4,000 per month.",
            [600000, 200000, 10000, 4000, 3000, 4000],
        )
        assert 600000.0 in result.all_numbers
        assert 200000.0 in result.all_numbers
        assert 10000.0 in result.all_numbers
        assert 4000.0 in result.all_numbers
        assert 3000.0 in result.all_numbers
        assert len(result.all_numbers) == 5

    def test_numbers_attached_to_arabic(self):
        result = heuristic_extract("عاوز اشتري عربية 9855وقب شهر 2000", [9855, 2000])
        assert 9855.0 in result.all_numbers
        assert 2000.0 in result.all_numbers

    def test_english_have_keyword_for_savings(self):
        result = heuristic_extract("I have 50000 in the bank", [50000])
        assert 50000.0 in result.all_numbers

    def test_take_home_keyword_for_income(self):
        result = heuristic_extract("My take home is 7000 per month", [7000])
        assert 7000.0 in result.all_numbers

    def test_arabic_multiple_numbers(self):
        result = heuristic_extract(
            "عايز سيارة 500000 مع مدخرات 100000 قبض شهري 20000 حوافز 4000 اضافي 3000 مصاريف 4000",
            [500000, 100000, 20000, 4000, 3000, 4000],
        )
        assert 500000.0 in result.all_numbers
        assert 100000.0 in result.all_numbers
        assert 20000.0 in result.all_numbers
        assert 4000.0 in result.all_numbers
        assert 3000.0 in result.all_numbers
        assert len(result.all_numbers) >= 5

    def test_arabic_urid_shira_araba(self):
        result = heuristic_extract(
            "اريد شراء عربة 800000ولدي ادخار300000 مرتب شهري 50000 مصاريف 10000 حوافز 4000 اضافي 2000",
            [800000, 300000, 50000, 10000, 4000, 2000],
        )
        assert 800000.0 in result.all_numbers
        assert 300000.0 in result.all_numbers
        assert 50000.0 in result.all_numbers
        assert 10000.0 in result.all_numbers
        assert 4000.0 in result.all_numbers
        assert 2000.0 in result.all_numbers

    def test_arabic_weekly_salary(self):
        result = heuristic_extract(
            "ريد شراء عربة 800000ولدي ادخار7000 مرتب اسبوعي 50000 مصاريف 10000 حوافز 4000 اضافي 2000",
            [800000, 7000, 50000, 10000, 4000, 2000],
        )
        assert 800000.0 in result.all_numbers
        assert 7000.0 in result.all_numbers
        assert 50000.0 in result.all_numbers
        assert 10000.0 in result.all_numbers
        assert 4000.0 in result.all_numbers
        assert 2000.0 in result.all_numbers

    def test_arabic_bikima_goal(self):
        result = heuristic_extract(
            "عايز اشتري سيارة بقيمة 30000 مدخرات 4000 قبض شهري 4000 حوافز 2000 مصاريف 3000",
            [30000, 4000, 4000, 2000, 3000],
        )
        assert 30000.0 in result.all_numbers
        assert 4000.0 in result.all_numbers
        assert 2000.0 in result.all_numbers
        assert 3000.0 in result.all_numbers


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


