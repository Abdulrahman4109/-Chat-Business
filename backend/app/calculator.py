import math
from .heuristics import apply_intelligent_defaults
from .models import CalculationResult, FinancialData


def calculate_goal(data: FinancialData) -> CalculationResult:
    data = apply_intelligent_defaults(data)
    goal_price = data.goal_price
    monthly_income = data.monthly_income or 0
    monthly_expenses = data.monthly_expenses or 0
    current_savings = data.current_savings or 0
    extra_income = data.extra_income or 0

    if goal_price is None:
        net_monthly_savings = monthly_income + extra_income - monthly_expenses
        return CalculationResult(
            net_monthly_savings=net_monthly_savings,
            remaining=0,
            months=None,
            raw_months=None,
            duration_display="goal amount not provided",
            is_achievable=False,
            suggestions=["Share a target price or goal amount to produce a timeline."],
        )

    net_monthly_savings = monthly_income + extra_income - monthly_expenses
    remaining = max(goal_price - current_savings, 0)

    if remaining == 0:
        return CalculationResult(
            net_monthly_savings=net_monthly_savings,
            remaining=0,
            months=0,
            raw_months=0,
            duration_display="already achieved",
            is_achievable=True,
            suggestions=["Your current savings already cover this goal."],
        )

    if net_monthly_savings <= 0:
        return CalculationResult(
            net_monthly_savings=net_monthly_savings,
            remaining=remaining,
            months=None,
            raw_months=None,
            duration_display="not achievable with current monthly savings",
            is_achievable=False,
            suggestions=[
                "Reduce monthly expenses or add recurring income before setting a timeline.",
                "Start by targeting a positive monthly savings amount.",
            ],
        )

    raw_months = remaining / net_monthly_savings
    months = math.ceil(raw_months)
    return CalculationResult(
        net_monthly_savings=net_monthly_savings,
        remaining=remaining,
        months=months,
        raw_months=raw_months,
        duration_display=format_duration(months),
        is_achievable=True,
        suggestions=build_suggestions(data, months, net_monthly_savings),
    )


def format_duration(months: int) -> str:
    if months < 12:
        return f"{months} month" if months == 1 else f"{months} months"
    if months == 12:
        return "1 year"
    years = months // 12
    rest = months % 12
    year_text = f"{years} year" if years == 1 else f"{years} years"
    if rest == 0:
        return year_text
    month_text = f"{rest} month" if rest == 1 else f"{rest} months"
    return f"{year_text} and {month_text}"


def build_suggestions(data: FinancialData, months: int, net_monthly_savings: float) -> list[str]:
    suggestions = [
        f"Keep at least {net_monthly_savings:,.0f} per month reserved for this goal.",
    ]
    if months > 12:
        suggestions.append("A small recurring income increase or expense reduction can shorten the timeline meaningfully.")
    if data.monthly_expenses and data.monthly_income and data.monthly_expenses > data.monthly_income * 0.6:
        suggestions.append("Your expenses are above 60% of income; reviewing fixed costs could improve savings speed.")
    if len(data.goals) > 1:
        suggestions.append("Prioritize one goal at a time or assign separate monthly savings targets to each goal.")
    return suggestions
