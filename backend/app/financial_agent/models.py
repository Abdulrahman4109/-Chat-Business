from uuid import uuid4
from datetime import datetime
from pydantic import BaseModel, Field


class FinancialAgentState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    goal: float | None = None
    goal_description: str = ""
    monthly_income: float | None = None
    monthly_expenses: float | None = None
    current_savings: float | None = None
    current_debts: float | None = None
    extra_income: float | None = None
    is_complete: bool = False
    latest_question: str = ""
    question_type: str = ""
    question_field: str = ""
    asked_fields: list[str] = Field(default_factory=list)
    messages: list[dict[str, str]] = Field(default_factory=list)
    result: dict | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class GuidedChatResponse(BaseModel):
    session_id: str
    assistant_message: dict
    latest_question: str
    question_type: str
    question_field: str
    is_complete: bool
    extracted_data: dict | None = None
    result: dict | None = None
