import math
from .models import RoiResult


def calculate_roi(development_cost: float, expected_monthly_return: float) -> RoiResult:
    if development_cost <= 0 or expected_monthly_return <= 0:
        return RoiResult(
            roi_months=0,
            duration_display="N/A",
            is_profitable=False,
            development_cost=development_cost,
            expected_monthly_return=expected_monthly_return,
        )

    months = math.ceil(development_cost / expected_monthly_return)
    return RoiResult(
        roi_months=months,
        duration_display=format_duration(months),
        is_profitable=True,
        development_cost=development_cost,
        expected_monthly_return=expected_monthly_return,
    )


def format_duration(months: float) -> str:
    if months < 1:
        return "less than a month"
    months_int = int(months)
    years = months_int // 12
    rem = months_int % 12
    if years == 0:
        return f"{rem} month{'s' if rem != 1 else ''}"
    if rem == 0:
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{years} year{'s' if years != 1 else ''} and {rem} month{'s' if rem != 1 else ''}"
