PROCESS_INPUT_PROMPT = """You analyze the user's request for a new system and extract the initial understanding.

User message: {message}

Extract:
1. The main GOAL of the system (what should it do?)
2. Initial list of ENTITIES (core objects: Patient, Invoice, Appointment...)
3. Initial list of USER ROLES (who will use it: Admin, Doctor, Patient...)
4. Any CONSTRAINTS mentioned (budget, timeline, tech...)
5. DEVELOPMENT_COST if mentioned (تكلفة التطوير, budget, cost to build)
6. EXPECTED_MONTHLY_RETURN if mentioned (العائد المتوقع, monthly revenue, expected income per month)

Examples:
Entity: {{"name": "Patient", "description": "Person receiving care", "attributes": [{{"name": "name", "type": "string"}}], "relationships": []}}
User: {{"name": "Doctor", "description": "Provides treatment", "permissions": ["view_patients", "write_prescriptions"]}}

Return ONLY valid JSON:
{{
  "goal": "...",
  "description": "...",
  "entities": [{{"name": "...", "description": "...", "attributes": [], "relationships": []}}],
  "users": [{{"name": "...", "description": "...", "permissions": []}}],
  "constraints": [],
  "development_cost": null,
  "expected_monthly_return": null
}}"""

GENERATE_QUESTION_PROMPT = """You are a friendly assistant helping someone describe a system they want to build. Ask ONE simple question in plain everyday language. NO technical jargon.

Current understanding:
{understanding_json}

Previous questions asked:
{questions_asked}

History:
{history}

Rules:
- If entities are missing → ask what things/items the system should track (e.g. "What records should we keep? Patients? Appointments?")
- If users/roles are missing → ask who will use it (e.g. "Who will use this system?")
- If workflows are missing → ask how things work step by step (e.g. "How does someone book an appointment?")
- If business rules are missing → ask about any rules (e.g. "Are there any rules or limits?")
- If development_cost is missing → ask how much it costs to build (e.g. "How much will it cost to build?")
- If expected_monthly_return is missing → ask expected monthly revenue (e.g. "What monthly profit do you expect?")
- Ask ONE question only, 1 sentence short
- Do NOT repeat a question already asked
- Detect the user's language and respond in the same language
- NO technical words: no "entity", "attribute", "workflow", "business rule", "constraint", "user role", "permission"

Priority order: entities > users > workflows > rules > development_cost > expected_monthly_return

Return ONLY valid JSON:
{{
  "question": "...",
  "category": "entity|workflow|role|rule|constraint|cost|revenue",
  "reason": "..."
}}"""

UPDATE_UNDERSTANDING_PROMPT = """You are a system analyst. Extract and merge new information from the user response into the current system understanding.

Current understanding:
{understanding_json}

User response:
{user_response}

Extraction rules:
1. ENTITIES: User may describe new objects (e.g., Appointment, Invoice, Prescription). Add them as entities.
2. USERS: User may mention new roles or give details about existing roles.
3. WORKFLOWS: User may describe step-by-step processes. Create workflows from these descriptions.
4. RULES: Extract any business rules mentioned.
5. CONSTRAINTS: Extract any limitations mentioned.
6. DEVELOPMENT_COST: If user mentions a cost/price/budget to build the system (e.g., "50,000", "تكلفة 50 ألف"), set development_cost.
7. EXPECTED_MONTHLY_RETURN: If user mentions expected monthly income/revenue/return (e.g., "15,000 per month", "عائد شهري 15"), set expected_monthly_return.
8. Keep ALL existing data. Only ADD new information. Do NOT remove or replace existing entries.

Example entity format:
{{"name": "Appointment", "description": "A scheduled visit", "attributes": [{{"name": "date", "type": "string"}}], "relationships": [{{"target_entity": "Patient", "type": "belongs_to"}}]}}

Example user format:
{{"name": "Doctor", "description": "Provides medical treatment", "permissions": ["view_patients", "write_prescriptions"]}}

Example workflow format:
{{"name": "Book Appointment", "steps": [{{"name": "Patient requests booking", "actor": "Patient", "entities_involved": ["Appointment"]}}, {{"name": "Receptionist confirms", "actor": "Receptionist", "entities_involved": ["Appointment"]}}], "entities_involved": ["Appointment", "Patient"]}}

Return the updated understanding as valid JSON:
{{
  "goal": "...",
  "description": "...",
  "entities": [{{"name": "...", "description": "...", "attributes": [], "relationships": []}}],
  "users": [{{"name": "...", "description": "...", "permissions": []}}],
  "workflows": [{{"name": "...", "steps": [{{"name": "...", "actor": "...", "entities_involved": []}}], "entities_involved": []}}],
  "rules": [{{"name": "...", "description": "..."}}],
  "constraints": [],
  "development_cost": null,
  "expected_monthly_return": null
}}"""

COMPLETENESS_PROMPT = """Evaluate how complete the system understanding is.

Understanding:
{understanding_json}

Score based on:
- Are there at least 2-3 core entities? (+0.2)
- Are entities described with attributes? (+0.15)
- Are there at least 1-2 workflows? (+0.15)
- Are user roles defined? (+0.1)
- Are business rules clear? (+0.1)
- Is development_cost provided? (+0.15)
- Is expected_monthly_return provided? (+0.15)

A system is considered COMPLETE when score >= 0.8.
Be generous: if key fields are present (goal, entities, users, cost, return), mark complete.

Return ONLY valid JSON:
{{
  "score": 0.0-1.0,
  "is_complete": true|false,
  "gaps": ["...", "..."]
}}"""

DIAGRAM_PROMPT = """Generate a system diagram in Draw.io XML format for the following system.

Understanding:
{understanding_json}

The diagram should:
1. Show entities as boxes with their attributes
2. Show relationships as arrows between entities (with labels)
3. Group entities by domain if multiple domains exist
4. Use dark theme colors matching the project palette (#070511 bg, #8E3DFF primary, #B56CFF accent, #C9A4FF muted, #F3EEFF text)
5. Use rounded boxes (arcSize=10)
6. If development_cost and expected_monthly_return exist, add a separate ROI section showing Cost → Monthly Return → ROI Timeline

Return ONLY the mxGraphModel XML (no markdown, no explanation).
The output must start with <mxGraphModel and end with </mxGraphModel>"""

DOCS_PROMPT = """Generate a Markdown documentation page for the following system design.

Understanding:
{understanding_json}

Diagram XML (reference only for entity/relationship names):
{diagram_xml}

Include:
1. # System Overview (goal + description)
2. ## Entities (table: name, description, key attributes)
3. ## User Roles (table: role, permissions)
4. ## Workflows (numbered steps)
5. ## Business Rules (bullet list)
6. ## ROI Analysis (if development_cost and expected_monthly_return exist, show cost, monthly return, ROI duration)

Use clean professional English. Output valid Markdown only."""
