import asyncio
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from pydantic import BaseModel, Field

from .calculator import calculate_goal
from .config import get_settings
from .diagram_generator import generate_financial_roadmap
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CalculateRequest,
    CalculationResult,
    ChatMessage,
    ChatRecord,
    ChatRequest,
    ChatResponse,
    DiagramRequest,
    FinancialData,
)
from .nlp import extract_numbers
from .system_builder.models import SystemBuilderState
from .system_builder.pipeline import SystemBuilderPipeline
from .financial_agent.models import FinancialAgentState
from .financial_agent.pipeline import FinancialAgentPipeline


class DiagramSaveRequest(BaseModel):
    conversation_id: str
    user_id: str = "default-user"
    xml: str


class SystemBuilderChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class SystemBuilderChatResponse(BaseModel):
    session_id: str
    understanding: dict
    latest_question: str
    is_complete: bool
    diagram_xml: str | None = None
    docs_markdown: str | None = None
    roi: dict | None = None
    messages: list[dict[str, str]] = Field(default_factory=list)


from .openai_service import OpenAIExtractionService
from .storage import MujarradStorage


app = FastAPI(title="Financial Chat Assistant", version="1.0.0")
settings = get_settings()

sessions: dict[str, SystemBuilderState] = {}
sb_pipeline = SystemBuilderPipeline()

guided_sessions: dict[str, FinancialAgentState] = {}
guided_pipeline = FinancialAgentPipeline()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{path:path}")
async def options_handler():
    return Response(status_code=200)

@app.post("/system-builder/chat", response_model=SystemBuilderChatResponse)
async def system_builder_chat(request: SystemBuilderChatRequest) -> SystemBuilderChatResponse:
    session_id = request.session_id or str(uuid4())
    if session_id not in sessions:
        sessions[session_id] = SystemBuilderState(session_id=session_id)

    state = sessions[session_id]
    state = await sb_pipeline.run_orchestrator(state, request.message)
    sessions[session_id] = state

    return SystemBuilderChatResponse(
        session_id=session_id,
        understanding=state.understanding.model_dump(),
        latest_question=state.latest_question,
        is_complete=state.is_complete,
        diagram_xml=state.diagram_xml,
        docs_markdown=state.docs_markdown,
        roi=state.roi.model_dump() if state.roi else None,
        messages=state.messages,
    )


@app.get("/system-builder/session/{session_id}")
async def system_builder_session(session_id: str) -> SystemBuilderChatResponse | dict:
    state = sessions.get(session_id)
    if not state:
        return {"error": "Session not found"}
    return SystemBuilderChatResponse(
        session_id=session_id,
        understanding=state.understanding.model_dump(),
        latest_question=state.latest_question,
        is_complete=state.is_complete,
        diagram_xml=state.diagram_xml,
        docs_markdown=state.docs_markdown,
        roi=state.roi.model_dump() if state.roi else None,
        messages=state.messages,
    )


@app.get("/system-builder/history")
async def system_builder_history() -> list[dict]:
    result = []
    for sid, state in sessions.items():
        first_msg = ""
        for m in state.messages:
            if m.get("role") == "user":
                first_msg = m["content"]
                break
        result.append({
            "session_id": sid,
            "goal": state.understanding.goal or first_msg[:80],
            "first_message": first_msg[:120] if first_msg else "",
            "is_complete": state.is_complete,
            "has_roi": state.roi is not None,
            "created_at": getattr(state, "created_at", ""),
        })
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return result


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    token_numbers = extract_numbers(request.message)
    try:
        data = await OpenAIExtractionService().extract(request.message, token_numbers)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Financial extraction failed: {exc}") from exc
    return AnalyzeResponse(data=data, token_numbers=token_numbers)


@app.post("/calculate", response_model=CalculationResult)
async def calculate(request: CalculateRequest) -> CalculationResult:
    return calculate_goal(request.data)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    conversation_id = request.conversation_id or str(uuid4())

    if conversation_id not in guided_sessions:
        guided_sessions[conversation_id] = FinancialAgentState(session_id=conversation_id)

    state = guided_sessions[conversation_id]
    state = await guided_pipeline.run_orchestrator(state, request.message)
    guided_sessions[conversation_id] = state

    extracted_data = FinancialData(
        goal_price=state.goal,
        monthly_income=state.monthly_income,
        monthly_expenses=state.monthly_expenses,
        current_savings=state.current_savings,
        current_debts=state.current_debts,
        extra_income=state.extra_income,
    )

    if state.is_complete and state.result:
        calc = CalculationResult(**state.result)
        assistant_text = build_assistant_response(calc, extracted_data)
        assistant_message = ChatMessage(
            role="assistant",
            content=assistant_text,
            extracted_data=extracted_data,
            calculation=calc,
        )

        record = ChatRecord(
            user_id=request.user_id,
            conversation_id=conversation_id,
            user_message=ChatMessage(role="user", content=request.message),
            assistant_message=assistant_message,
            extracted_data=extracted_data,
            calculation=calc,
        )
        asyncio.create_task(_store_chat_record_async(record))

        return ChatResponse(
            conversation_id=conversation_id,
            assistant_message=assistant_message,
            extracted_data=extracted_data,
            calculation=calc,
            is_complete=True,
        )

    last_msg = state.messages[-1] if state.messages else {"content": ""}
    assistant_message = ChatMessage(
        role="assistant",
        content=last_msg.get("content", ""),
        extracted_data=extracted_data,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        assistant_message=assistant_message,
        extracted_data=extracted_data,
        question_type=state.question_type,
        question_field=state.question_field,
        is_complete=False,
    )


async def _store_chat_record_async(record: ChatRecord) -> None:
    try:
        storage = MujarradStorage()
        await storage.save_chat_record(record)
    except Exception as e:
        print("Background storage error:", e)



@app.get("/history")
async def history(
    user_id: str = Query(default="default-user", min_length=1, max_length=128)
):
    try:
        storage = MujarradStorage()
        records = await storage.get_history(user_id)

        formatted = records[:]

        return formatted

    except Exception as e:
        print("History error:", e)
        return []


@app.post("/diagram")
async def diagram(request: DiagramRequest) -> dict[str, str]:
    xml = generate_financial_roadmap(request.data, request.calculation)
    return {"xml": xml}


@app.post("/diagram/save")
async def diagram_save(request: DiagramSaveRequest) -> dict[str, bool]:
    try:
        storage = MujarradStorage()
        await storage.save_diagram_node(request.conversation_id, request.user_id, request.xml)
        return {"success": True}
    except Exception as e:
        print("Diagram save error:", e)
        return {"success": False}


@app.get("/diagram/load")
async def diagram_load(
    conversation_id: str = Query(min_length=1),
    user_id: str = Query(default="default-user"),
) -> dict:
    try:
        storage = MujarradStorage()
        xml = await storage.get_diagram_node(conversation_id, user_id)
        return {"xml": xml}
    except Exception as e:
        print("Diagram load error:", e)
        return {"xml": None}


@app.post("/system-builder/roi/save")
async def system_builder_roi_save(request: SystemBuilderChatRequest) -> dict[str, bool]:
    if not request.session_id or request.session_id not in sessions:
        return {"success": False}
    try:
        state = sessions[request.session_id]
        storage = MujarradStorage()
        roi_data = state.roi.model_dump() if state.roi else {}
        await storage.save_roi_node(request.session_id, roi_data)
        return {"success": True}
    except Exception as e:
        print("ROI save error:", e)
        return {"success": False}


@app.get("/mujarrad/status")
async def mujarrad_status():
    try:
        storage = MujarradStorage()
        return await storage.check_connection()
    except Exception as e:
        return {"connected": False, "error": str(e)}


def build_assistant_response(calculation: CalculationResult, data=None) -> str:
    if not calculation.is_achievable:
        return (
            f"I could not produce a reliable timeline yet: {calculation.duration_display}. "
            f"{' '.join(calculation.suggestions)}"
        )

    if calculation.months == 0:
        return "Your goal is already funded with your current savings."

    parts = [
        f"At your current pace, it will take {calculation.duration_display}.",
        f"Net monthly savings: {calculation.net_monthly_savings:,.0f}.",
    ]
    if data and data.current_debts:
        net_savings = (data.current_savings or 0) - data.current_debts
        parts.append(f"Net savings: {net_savings:,.0f} (savings {data.current_savings:,.0f} - debts {data.current_debts:,.0f}).")
    parts.append(f"Remaining amount: {calculation.remaining:,.0f}.")
    parts.extend(calculation.suggestions)
    return " ".join(parts)