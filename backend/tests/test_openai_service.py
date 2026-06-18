import pytest
from app.heuristics import heuristic_extract
from app.models import FinancialData
from app.openai_service import _aggregate_segment_extractions


class TestExtractionFallback:
    def test_heuristic_gives_reasonable_default(self):
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

    def test_heuristic_handles_attached_arabic_numbers(self):
        result = heuristic_extract("عاوز اشتري عربية 9855وقب شهر 2000", [9855, 2000])
        assert 9855.0 in result.all_numbers
        assert 2000.0 in result.all_numbers

    def test_heuristic_with_english_have_savings(self):
        result = heuristic_extract("I have 30000 saved for a car", [30000])
        assert 30000.0 in result.all_numbers


class TestAggregateSegmentExtractions:
    def test_empty_extractions(self):
        result = _aggregate_segment_extractions([], [], [])
        assert result.goal_price is None
        assert result.monthly_income is None
        assert result.goals == []
        assert result.segments == []

    def test_single_field_extraction(self):
        extractions = [{"segment_index": 0, "field": "monthly_income", "value": 5000}]
        result = _aggregate_segment_extractions(extractions, [5000], ["I earn 5000"])
        assert result.monthly_income == 5000.0
        assert len(result.segments) == 1
        assert result.segments[0]["text"] == "I earn 5000"
        assert result.segments[0]["classifications"] == [{"field": "monthly_income", "value": 5000}]

    def test_multiple_fields_same_segment(self):
        extractions = [
            {"segment_index": 0, "field": "monthly_income", "value": 5000},
            {"segment_index": 0, "field": "monthly_expenses", "value": 1500},
        ]
        result = _aggregate_segment_extractions(extractions, [5000, 1500], ["I earn 5000 spend 1500"])
        assert result.monthly_income == 5000.0
        assert result.monthly_expenses == 1500.0
        assert len(result.segments) == 1
        assert len(result.segments[0]["classifications"]) == 2

    def test_sum_same_field_across_segments(self):
        extractions = [
            {"segment_index": 0, "field": "extra_income", "value": 1000},
            {"segment_index": 1, "field": "extra_income", "value": 2000},
        ]
        segments_text = ["bonus 1000", "side 2000"]
        result = _aggregate_segment_extractions(extractions, [1000, 2000], segments_text)
        assert result.extra_income == 3000.0
        assert len(result.segments) == 2
        assert result.segments[0]["classifications"][0]["field"] == "extra_income"
        assert result.segments[1]["classifications"][0]["field"] == "extra_income"

    def test_multiple_goals_largest_wins(self):
        extractions = [
            {"segment_index": 0, "field": "goal_price", "value": 30000},
            {"segment_index": 1, "field": "goal_price", "value": 50000},
        ]
        segments_text = ["car 30000", "house 50000"]
        result = _aggregate_segment_extractions(extractions, [30000, 50000], segments_text)
        assert result.goal_price == 50000.0
        assert len(result.goals) == 2
        assert len(result.segments) == 2

    def test_full_financial_picture(self):
        extractions = [
            {"segment_index": 0, "field": "goal_price", "value": 600000},
            {"segment_index": 1, "field": "current_savings", "value": 200000},
            {"segment_index": 2, "field": "monthly_income", "value": 10000},
            {"segment_index": 3, "field": "extra_income", "value": 4000},
            {"segment_index": 4, "field": "extra_income", "value": 3000},
            {"segment_index": 5, "field": "monthly_expenses", "value": 4000},
        ]
        result = _aggregate_segment_extractions(
            extractions,
            [600000, 200000, 10000, 4000, 3000, 4000],
            ["car worth 600000", "200000 savings", "salary 10000", "bonuses 4000", "extra 3000", "expenses 4000"],
        )
        assert result.goal_price == 600000.0
        assert result.current_savings == 200000.0
        assert result.monthly_income == 10000.0
        assert result.extra_income == 7000.0
        assert result.monthly_expenses == 4000.0
        assert len(result.goals) == 1
        assert len(result.segments) == 6

    def test_non_financial_segments_have_empty_classifications(self):
        extractions = [
            {"segment_index": 0, "field": "monthly_income", "value": 5000},
        ]
        segments_text = ["I earn 5000", "Hello how are you", "Thanks"]
        result = _aggregate_segment_extractions(extractions, [5000], segments_text)
        assert len(result.segments) == 3
        assert len(result.segments[0]["classifications"]) == 1
        assert result.segments[1]["classifications"] == []
        assert result.segments[2]["classifications"] == []

    def test_skip_invalid_value(self):
        extractions = [
            {"segment_index": 0, "field": "monthly_income", "value": "not-a-number"},
            {"segment_index": 1, "field": "monthly_income", "value": 5000},
        ]
        result = _aggregate_segment_extractions(extractions, [5000], ["invalid", "earn 5000"])
        assert result.monthly_income == 5000.0

    def test_skip_missing_field(self):
        extractions = [
            {"segment_index": 0, "value": 5000},
            {"segment_index": 1, "field": None, "value": 3000},
        ]
        result = _aggregate_segment_extractions(extractions, [], ["no field", "null field"])
        assert result.monthly_income is None

    def test_uses_all_numbers(self):
        result = _aggregate_segment_extractions([], [1000, 2000, 3000], [])
        assert result.all_numbers == [1000.0, 2000.0, 3000.0]
