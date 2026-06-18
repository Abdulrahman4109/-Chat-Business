from app.calculator import calculate_goal, format_duration
from app.models import FinancialData


class TestCalculateGoal:
    def test_achievable_goal(self):
        data = FinancialData(
            goal_price=50000.0,
            monthly_income=10000.0,
            monthly_expenses=5000.0,
            current_savings=10000.0,
        )
        result = calculate_goal(data)
        assert result.is_achievable is True
        assert result.remaining == 40000.0
        assert result.months == 8
        assert result.net_monthly_savings == 5000.0

    def test_already_funded(self):
        data = FinancialData(
            goal_price=10000.0,
            monthly_income=5000.0,
            monthly_expenses=3000.0,
            current_savings=10000.0,
        )
        result = calculate_goal(data)
        assert result.is_achievable is True
        assert result.months == 0

    def test_no_goal(self):
        data = FinancialData(monthly_income=5000.0, monthly_expenses=3000.0)
        result = calculate_goal(data)
        assert result.is_achievable is False
        assert "not provided" in result.duration_display

    def test_negative_savings(self):
        data = FinancialData(
            goal_price=50000.0,
            monthly_income=3000.0,
            monthly_expenses=4000.0,
        )
        result = calculate_goal(data)
        assert result.is_achievable is False
        assert "not achievable" in result.duration_display

    def test_with_extra_income(self):
        data = FinancialData(
            goal_price=60000.0,
            monthly_income=8000.0,
            monthly_expenses=4000.0,
            current_savings=0,
            extra_income=2000.0,
        )
        result = calculate_goal(data)
        assert result.is_achievable is True
        assert result.net_monthly_savings == 6000.0
        assert result.months == 10


class TestFormatDuration:
    def test_months(self):
        assert format_duration(5) == "5 months"

    def test_one_month(self):
        assert format_duration(1) == "1 month"

    def test_one_year(self):
        assert format_duration(12) == "1 year"

    def test_years_and_months(self):
        assert "years" in format_duration(30)
        assert "months" in format_duration(30)

    def test_exact_years(self):
        assert format_duration(24) == "2 years"