# Financial Chat Assistant

A conversational AI that extracts financial goals from natural language, asks for missing information, and calculates a timeline to reach the goal.

## How It Works

1. User sends a message about their financial goal
2. The system extracts numbers (goal amount, income, expenses, etc.)
3. If any information is missing, it asks a yes/no question
4. Once all data is collected, it calculates the timeline
5. Result is displayed with an optional visual roadmap diagram

## Quick Links

| Document | Content |
|----------|---------|
| [01-architecture.md](01-architecture.md) | Project structure, request lifecycle, data flow |
| [02-backend-api.md](02-backend-api.md) | All HTTP endpoints, request/response schemas |
| [03-ai-pipeline.md](03-ai-pipeline.md) | Number extraction, normalization, calculation |
| [04-storage.md](04-storage.md) | Local JSON + remote API storage |
| [05-frontend.md](05-frontend.md) | React components, state, user interaction |
| [06-financial-agent.md](06-financial-agent.md) | State machine, prompts, conversation flow |
| [07-diagram.md](07-diagram.md) | Draw.io roadmap diagram integration |
