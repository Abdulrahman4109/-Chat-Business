import json
import re
from openai import AsyncOpenAI
from .models import SystemBuilderState, SystemUnderstanding, UserRole, SystemEntity, Workflow, BusinessRule, RoiResult
from .prompts import (
    PROCESS_INPUT_PROMPT,
    GENERATE_QUESTION_PROMPT,
    UPDATE_UNDERSTANDING_PROMPT,
    COMPLETENESS_PROMPT,
    DIAGRAM_PROMPT,
    DOCS_PROMPT,
)
from .drawio import generate_system_diagram
from .calculator import calculate_roi
from ..config import get_settings


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        text = text[brace_start : brace_end + 1]
    return json.loads(text)


class SystemBuilderPipeline:
    def __init__(self):
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

    async def process_input(self, state: SystemBuilderState, message: str) -> SystemBuilderState:
        raw = await self._llm_call(PROCESS_INPUT_PROMPT.format(message=message), message)
        try:
            parsed = _parse_json(raw)
            u = state.understanding
            u.goal = parsed.get("goal", u.goal)
            u.description = parsed.get("description", u.description)
            for e_data in parsed.get("entities", []):
                if not any(e.name == e_data["name"] for e in u.entities):
                    u.entities.append(SystemEntity(**e_data))
            for r_data in parsed.get("users", []):
                if not any(u2.name == r_data["name"] for u2 in u.users):
                    u.users.append(UserRole(**r_data))
            u.constraints = list(set(u.constraints + parsed.get("constraints", [])))
            cost = parsed.get("development_cost")
            if cost is not None:
                u.development_cost = float(cost)
            ret = parsed.get("expected_monthly_return")
            if ret is not None:
                u.expected_monthly_return = float(ret)
        except Exception:
            pass
        state.messages.append({"role": "user", "content": message})
        return state

    async def generate_question(self, state: SystemBuilderState) -> SystemBuilderState:
        if not self.client:
            state.latest_question = "Tell me more about your system — what are the main entities and who will use it?"
            return state

        raw = await self._llm_call(
            GENERATE_QUESTION_PROMPT.format(
                understanding_json=state.understanding.model_dump_json(indent=2),
                questions_asked=json.dumps(state.understanding.questions_asked),
                history=json.dumps(state.messages[-4:]),
            ),
            "Ask one question to clarify the system design.",
        )
        try:
            parsed = _parse_json(raw)
            question = parsed.get("question", "")
            if question:
                state.latest_question = question
                state.understanding.questions_asked.append(question)
        except Exception:
            state.latest_question = "Could you describe the main entities and workflows in your system?"
        return state

    async def update_understanding(self, state: SystemBuilderState, response: str) -> SystemBuilderState:
        raw = await self._llm_call(
            UPDATE_UNDERSTANDING_PROMPT.format(
                understanding_json=state.understanding.model_dump_json(indent=2),
                user_response=response,
            ),
            response,
        )
        try:
            parsed = _parse_json(raw)
            u = state.understanding
            if parsed.get("goal"):
                u.goal = parsed["goal"]
            if parsed.get("description"):
                u.description = parsed["description"]
            for e_data in parsed.get("entities", []):
                if not any(e.name == e_data["name"] for e in u.entities):
                    u.entities.append(SystemEntity(**e_data))
                else:
                    for e in u.entities:
                        if e.name == e_data["name"] and e_data.get("attributes"):
                            e.attributes = e.attributes or []
                            for a in e_data["attributes"]:
                                if a not in [a2.model_dump() for a2 in e.attributes]:
                                    from .models import EntityAttribute
                                    e.attributes.append(EntityAttribute(**a))
            for r_data in parsed.get("users", []):
                if not any(u2.name == r_data["name"] for u2 in u.users):
                    u.users.append(UserRole(**r_data))
            for w_data in parsed.get("workflows", []):
                if not any(w.name == w_data["name"] for w in u.workflows):
                    u.workflows.append(Workflow(**w_data))
            for r_data in parsed.get("rules", []):
                if not any(r.name == r_data["name"] for r in u.rules):
                    u.rules.append(BusinessRule(**r_data))
            u.constraints = list(set(u.constraints + parsed.get("constraints", [])))
            cost = parsed.get("development_cost")
            if cost is not None:
                u.development_cost = float(cost)
            ret = parsed.get("expected_monthly_return")
            if ret is not None:
                u.expected_monthly_return = float(ret)
        except Exception as e:
            print("Update understanding error:", e, "| Raw:", raw[:200])
        state.latest_response = response
        state.messages.append({"role": "user", "content": response})
        return state

    async def check_completeness(self, state: SystemBuilderState) -> SystemBuilderState:
        fallback = self._fallback_score(state.understanding)

        if not self.client:
            state.understanding.completeness_score = fallback
            state.is_complete = fallback >= 0.8
            return state

        raw = await self._llm_call(
            COMPLETENESS_PROMPT.format(
                understanding_json=state.understanding.model_dump_json(indent=2)
            ),
            "Evaluate completeness.",
        )
        try:
            parsed = _parse_json(raw)
            llm_score = parsed.get("score", 0)
            llm_complete = parsed.get("is_complete", False)
            state.understanding.completeness_score = max(llm_score, fallback)
            state.is_complete = llm_complete or fallback >= 0.8
        except Exception:
            state.understanding.completeness_score = fallback
            state.is_complete = fallback >= 0.8
        return state

    def _fallback_score(self, u: SystemUnderstanding) -> float:
        score = 0.0
        if len(u.entities) >= 2:
            score += 0.2
        has_attr = any(len(e.attributes) > 0 for e in u.entities)
        if has_attr:
            score += 0.15
        if len(u.workflows) >= 1:
            score += 0.15
        if len(u.users) >= 1:
            score += 0.1
        if len(u.rules) >= 1:
            score += 0.1
        if u.development_cost is not None and u.development_cost > 0:
            score += 0.15
        if u.expected_monthly_return is not None and u.expected_monthly_return > 0:
            score += 0.15
        return score

    async def generate_diagram(self, state: SystemBuilderState) -> SystemBuilderState:
        if not self.client:
            state.diagram_xml = generate_system_diagram(state.understanding, state.roi)
            return state

        raw = await self._llm_call(
            DIAGRAM_PROMPT.format(
                understanding_json=state.understanding.model_dump_json(indent=2)
            ),
            "Generate the diagram.",
        )
        if raw.strip().startswith("<mxGraphModel"):
            state.diagram_xml = raw.strip()
        else:
            state.diagram_xml = generate_system_diagram(state.understanding, state.roi)
        return state

    async def generate_docs(self, state: SystemBuilderState) -> SystemBuilderState:
        if not self.client:
            state.docs_markdown = self._fallback_docs(state.understanding)
            return state

        raw = await self._llm_call(
            DOCS_PROMPT.format(
                understanding_json=state.understanding.model_dump_json(indent=2),
                diagram_xml=(state.diagram_xml or "")[:2000],
            ),
            "Generate documentation.",
        )
        if raw.strip().startswith("#"):
            state.docs_markdown = raw.strip()
        else:
            state.docs_markdown = self._fallback_docs(state.understanding)
        return state

    def _fallback_docs(self, u: SystemUnderstanding) -> str:
        lines = [f"# {u.goal}", "", u.description, ""]
        if u.entities:
            lines.append("## Entities")
            lines.append("| Name | Description | Attributes |")
            lines.append("|------|-------------|------------|")
            for e in u.entities:
                attrs = ", ".join(a.name for a in e.attributes) if e.attributes else "-"
                lines.append(f"| {e.name} | {e.description} | {attrs} |")
            lines.append("")
        if u.users:
            lines.append("## User Roles")
            for r in u.users:
                perms = ", ".join(r.permissions) if r.permissions else "-"
                lines.append(f"- **{r.name}**: {r.description} (permissions: {perms})")
            lines.append("")
        if u.workflows:
            lines.append("## Workflows")
            for w in u.workflows:
                lines.append(f"### {w.name}")
                for i, s in enumerate(w.steps, 1):
                    lines.append(f"{i}. {s.name} — {s.description}")
            lines.append("")
        if u.rules:
            lines.append("## Business Rules")
            for r in u.rules:
                lines.append(f"- **{r.name}**: {r.description}")
            lines.append("")
        if u.development_cost is not None or u.expected_monthly_return is not None:
            lines.append("## ROI Analysis")
            if u.development_cost is not None:
                lines.append(f"- **Development Cost**: ${u.development_cost:,.0f}")
            if u.expected_monthly_return is not None:
                lines.append(f"- **Expected Monthly Return**: ${u.expected_monthly_return:,.0f}")
            if u.development_cost and u.expected_monthly_return and u.expected_monthly_return > 0:
                from .calculator import calculate_roi
                roi = calculate_roi(u.development_cost, u.expected_monthly_return)
                lines.append(f"- **ROI Timeline**: {roi.duration_display}")
                lines.append(f"- **Profitable**: {'Yes' if roi.is_profitable else 'No'}")
        return "\n".join(lines)

    async def run_orchestrator(self, state: SystemBuilderState, user_message: str) -> SystemBuilderState:
        if not state.understanding.goal:
            state = await self.process_input(state, user_message)
        else:
            state = await self.update_understanding(state, user_message)

        state = await self.check_completeness(state)

        if state.is_complete:
            if (state.understanding.development_cost is not None and
                state.understanding.expected_monthly_return is not None):
                state.roi = calculate_roi(
                    state.understanding.development_cost,
                    state.understanding.expected_monthly_return,
                )
            state = await self.generate_diagram(state)
            state = await self.generate_docs(state)
            state.latest_question = ""
        else:
            state = await self.generate_question(state)

        return state
