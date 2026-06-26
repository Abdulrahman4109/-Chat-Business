import json
import re
from openai import AsyncOpenAI
from .models import FinancialAgentState
from .prompts import PROCESS_INPUT_PROMPT, UPDATE_DATA_PROMPT
from ..calculator import calculate_goal
from ..models import FinancialData
from ..heuristics import normalize_text

FIELD_ORDER = ['monthly_expenses', 'current_savings', 'current_debts', 'extra_income']

FIELD_QUESTIONS = {
    'monthly_expenses': {
        'en': 'Do you have any monthly expenses?',
        'ar': 'هل لديك مصاريف شهرية؟',
    },
    'current_savings': {
        'en': 'Do you have any savings?',
        'ar': 'هل لديك مدخرات؟',
    },
    'current_debts': {
        'en': 'Do you have any debts or loans?',
        'ar': 'هل لديك ديون؟',
    },
    'extra_income': {
        'en': 'Do you have any extra monthly income?',
        'ar': 'هل لديك حوافز إضافية؟',
    },
}


def _detect_language(messages: list[dict]) -> str:
    for m in reversed(messages):
        text = m.get("content", "") if isinstance(m, dict) else str(m)
        if re.search(r'[\u0600-\u06FF]', text):
            return 'ar'
    return 'en'


def _parse_json(text: str) -> dict:
    text = normalize_text(text)
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        text = text[brace_start : brace_end + 1]
    return json.loads(text)


class FinancialAgentPipeline:
    def __init__(self):
        from ..config import get_settings
        settings = get_settings()
        self.model = settings.openai_model
        if settings.openai_api_key:
            client_kwargs = {"api_key": settings.openai_api_key}
            if settings.openai_base_url:
                client_kwargs["base_url"] = settings.openai_base_url
            self.client = AsyncOpenAI(**client_kwargs)
        else:
            self.client = None

    async def _llm_call(self, system_prompt: str, user_message: str) -> str:
        if self.client is None:
            return "{}"
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            timeout=20,
        )
        return response.choices[0].message.content or "{}"

    async def process_input(self, state: FinancialAgentState, message: str) -> FinancialAgentState:
        normalized = normalize_text(message)
        raw = await self._llm_call(
            PROCESS_INPUT_PROMPT.format(message=normalized), normalized
        )
        try:
            parsed = _parse_json(raw) if raw.strip() and raw != "{}" else {}
            if parsed.get("goal") is not None:
                state.goal = float(parsed["goal"])
            state.goal_description = parsed.get("goal_description", "")
            if parsed.get("monthly_income") is not None:
                state.monthly_income = float(parsed["monthly_income"])
            if parsed.get("monthly_expenses") is not None:
                state.monthly_expenses = float(parsed["monthly_expenses"])
            if parsed.get("current_savings") is not None:
                state.current_savings = float(parsed["current_savings"])
            if parsed.get("current_debts") is not None:
                state.current_debts = float(parsed["current_debts"])
            if parsed.get("extra_income") is not None:
                state.extra_income = float(parsed["extra_income"])
        except Exception:
            pass
        state.messages.append({"role": "user", "content": message})
        return state

    def generate_question(self, state: FinancialAgentState) -> FinancialAgentState:
        lang = _detect_language(state.messages)
        for field in FIELD_ORDER:
            if getattr(state, field) is None and field not in state.asked_fields:
                state.latest_question = FIELD_QUESTIONS[field].get(lang, FIELD_QUESTIONS[field]['en'])
                state.question_type = "yesno"
                state.question_field = field
                state.asked_fields.append(field)
                return state

        state.latest_question = ""
        state.question_type = ""
        state.question_field = ""
        return state

    async def update_data(self, state: FinancialAgentState, answer: str) -> FinancialAgentState:
        normalized = normalize_text(answer)
        raw = await self._llm_call(
            UPDATE_DATA_PROMPT.format(
                data_json=state.model_dump_json(indent=2),
                field=state.question_field,
                answer=normalized,
            ),
            normalized,
        )
        try:
            parsed = _parse_json(raw)
            value = float(parsed.get("value", 0))
            setattr(state, state.question_field, value)
        except Exception:
            setattr(state, state.question_field, 0)
        state.messages.append({"role": "user", "content": answer})
        state.latest_question = ""
        state.question_type = ""
        state.question_field = ""
        return state

    def check_completeness(self, state: FinancialAgentState) -> FinancialAgentState:
        has_required = (
            state.goal is not None
            and state.monthly_income is not None
            and state.monthly_expenses is not None
        )
        has_optional = all(
            getattr(state, field) is not None
            for field in FIELD_ORDER
        )
        state.is_complete = bool(has_required and has_optional)
        return state

    def _build_data(self, state: FinancialAgentState) -> FinancialData:
        return FinancialData(
            goal_price=state.goal or 0,
            monthly_income=state.monthly_income or 0,
            monthly_expenses=state.monthly_expenses or 0,
            current_savings=state.current_savings,
            current_debts=state.current_debts,
            extra_income=state.extra_income,
        )

    async def run_orchestrator(self, state: FinancialAgentState, message: str) -> FinancialAgentState:
        if state.goal is None and state.monthly_income is None:
            state = await self.process_input(state, message)
        else:
            state = await self.update_data(state, message)

        state = self.check_completeness(state)

        if state.is_complete:
            data = self._build_data(state)
            calc = calculate_goal(data)
            state.result = calc.model_dump()
            state.latest_question = ""
            state.question_type = ""
            state.question_field = ""

            msg = f"Done! {calc.duration_display}"
            if calc.net_monthly_savings:
                msg += f" — Net monthly savings: ${calc.net_monthly_savings:,.0f}"
            state.messages.append({"role": "assistant", "content": msg, "result": calc.model_dump()})
        else:
            state = self.generate_question(state)
            if state.latest_question:
                state.messages.append({
                    "role": "assistant",
                    "content": state.latest_question,
                    "question_type": "yesno",
                    "question_field": state.question_field,
                })

        return state
