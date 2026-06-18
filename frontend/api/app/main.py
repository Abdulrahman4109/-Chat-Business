from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .calculator import calculate_goal
from .config import get_settings
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CalculateRequest,
    CalculationResult,
    ChatMessage,
    ChatRecord,
    ChatRequest,
    ChatResponse,
)
from .nlp import extract_numbers
from .openai_service import OpenAIExtractionService
from .storage import MujarradStorage


app = FastAPI(title="Financial Chat Assistant", version="1.0.0")
settings = get_settings()

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

    token_numbers = extract_numbers(request.message)

    try:
        extracted = await OpenAIExtractionService().extract(request.message, token_numbers)
        calculation = calculate_goal(extracted)

        assistant_text = build_assistant_response(calculation)

        user_message = ChatMessage(role="user", content=request.message)

        assistant_message = ChatMessage(
            role="assistant",
            content=assistant_text,
            extracted_data=extracted,
            calculation=calculation,
        )

        record = ChatRecord(
            user_id=request.user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            assistant_message=assistant_message,
            extracted_data=extracted,
            calculation=calculation,
        )

        # ✅ حفظ السجل بشكل صريح
        try:
            storage = MujarradStorage()
            await storage.save_chat_record(record)
        except Exception as e:
            print("Storage error:", e)
            assistant_message.content += " (history not saved)"

        return ChatResponse(
            conversation_id=conversation_id,
            assistant_message=assistant_message,
            extracted_data=extracted,
            calculation=calculation,
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat processing failed: {exc}") from exc



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


@app.get("/mujarrad/status")
async def mujarrad_status():
    try:
        storage = MujarradStorage()
        return await storage.check_connection()
    except Exception as e:
        return {"connected": False, "error": str(e)}


def build_assistant_response(calculation: CalculationResult) -> str:
    if not calculation.is_achievable:
        return (
            f"I could not produce a reliable timeline yet: {calculation.duration_display}. "
            f"{' '.join(calculation.suggestions)}"
        )

    if calculation.months == 0:
        return "Your goal is already funded with your current savings."

    return (
        f"At your current pace, it will take {calculation.duration_display}. "
        f"Net monthly savings: {calculation.net_monthly_savings:,.0f}. "
        f"Remaining amount: {calculation.remaining:,.0f}. "
        f"{' '.join(calculation.suggestions)}"
    )