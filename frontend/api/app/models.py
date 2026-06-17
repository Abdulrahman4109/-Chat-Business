from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    user_id: str = Field(default="default-user", min_length=1, max_length=128)
    conversation_id: str | None = None


class AnalyzeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class FinancialData(BaseModel):
    goal_price: float | None = None
    monthly_income: float | None = None
    monthly_expenses: float | None = None
    current_savings: float | None = 0
    extra_income: float | None = 0
    goals: list[dict[str, Any]] = Field(default_factory=list)
    all_numbers: list[float] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("goal_price", "monthly_income", "monthly_expenses", "current_savings", "extra_income")
    @classmethod
    def non_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("Financial values must be non-negative")
        return value


class AnalyzeResponse(BaseModel):
    data: FinancialData
    token_numbers: list[float]


class CalculateRequest(BaseModel):
    data: FinancialData


class CalculationResult(BaseModel):
    net_monthly_savings: float
    remaining: float
    months: int | None
    raw_months: float | None
    duration_display: str
    is_achievable: bool
    suggestions: list[str]


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extracted_data: FinancialData | None = None
    calculation: CalculationResult | None = None


class ChatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    conversation_id: str
    user_message: ChatMessage
    assistant_message: ChatMessage
    extracted_data: FinancialData
    calculation: CalculationResult
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChatResponse(BaseModel):
    conversation_id: str
    assistant_message: ChatMessage
    extracted_data: FinancialData
    calculation: CalculationResult

