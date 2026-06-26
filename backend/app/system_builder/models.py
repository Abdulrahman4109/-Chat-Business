from typing import Any
from uuid import uuid4
from pydantic import BaseModel, Field


class EntityAttribute(BaseModel):
    name: str
    type: str = "string"
    required: bool = False


class Relationship(BaseModel):
    target_entity: str
    type: str = "one-to-many"
    description: str = ""


class SystemEntity(BaseModel):
    name: str
    description: str = ""
    attributes: list[EntityAttribute] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    name: str
    description: str = ""
    actor: str = ""
    entities_involved: list[str] = Field(default_factory=list)


class Workflow(BaseModel):
    name: str
    steps: list[WorkflowStep] = Field(default_factory=list)
    entities_involved: list[str] = Field(default_factory=list)


class BusinessRule(BaseModel):
    name: str
    description: str = ""


class UserRole(BaseModel):
    name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class RoiResult(BaseModel):
    roi_months: float
    duration_display: str
    is_profitable: bool
    development_cost: float
    expected_monthly_return: float


class SystemUnderstanding(BaseModel):
    goal: str = ""
    description: str = ""
    users: list[UserRole] = Field(default_factory=list)
    entities: list[SystemEntity] = Field(default_factory=list)
    workflows: list[Workflow] = Field(default_factory=list)
    rules: list[BusinessRule] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    development_cost: float | None = None
    expected_monthly_return: float | None = None
    questions_asked: list[str] = Field(default_factory=list)
    completeness_score: float = 0.0


class SystemBuilderResponse(BaseModel):
    session_id: str
    understanding: SystemUnderstanding
    latest_question: str = ""
    is_complete: bool = False
    diagram_xml: str | None = None
    docs_markdown: str | None = None
    roi: RoiResult | None = None
    messages: list[dict[str, str]] = Field(default_factory=list)


class SystemBuilderState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    understanding: SystemUnderstanding = Field(default_factory=SystemUnderstanding)
    latest_question: str = ""
    latest_response: str = ""
    is_complete: bool = False
    diagram_xml: str | None = None
    docs_markdown: str | None = None
    roi: RoiResult | None = None
    messages: list[dict[str, str]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())
