# Financial Roadmap Diagram

Integration with [draw.io](https://www.draw.io) (diagrams.net) for visual financial roadmap generation.

## API

### POST `/diagram` — Generate
**Input:** `{ data: FinancialData, calculation: CalculationResult }`
**Output:** `{ xml: "<mxGraphModel>..." }`

### POST `/diagram/save` — Persist
**Input:** `{ conversation_id, user_id, xml }`
**Output:** `{ success: true }`

### GET `/diagram/load` — Retrieve
**Query:** `?conversation_id=...&user_id=...`
**Output:** `{ xml: "..." }` or `{ xml: null }`

## Diagram Layout

Nodes arranged vertically with directional arrows:

```
┌─────────────────┐
│  Financial Road  │
│     Map          │
└────────┬─────────┘
         ▼
┌─────────────────┐
│  Goal: 800,000   │  (blue)
└────────┬─────────┘
         ▼
┌─────────────────┐
│  Income: 15,000  │  (green)
│  Extra: 2,000    │
└────────┬─────────┘
         ▼
┌─────────────────┐
│  Expenses: 8,000 │  (red)
└────────┬─────────┘
         ▼
┌─────────────────┐
│  Savings: 10,000 │  (blue)
│  Debts: 5,000    │  (red, if > 0)
└────────┬─────────┘
         ▼
┌─────────────────┐
│  Timeline:       │  (purple)
│  3 years 5 mo    │
└─────────────────┘
```

## Frontend Modal

### State
| Variable | Purpose |
|----------|---------|
| `diagramOpen` | Modal visibility |
| `diagramLoading` | Loading indicator during XML generation |
| `diagramFrameRef` | iframe DOM reference for postMessage |
| `diagramXmlRef` | Current XML content |

### Flow
1. User clicks "View Financial Plan" → POST `/diagram` → store XML in `diagramXmlRef` → open modal
2. iframe loads `https://embed.diagrams.net?embed=1&ui=dark&save=1&proto=json`
3. draw.io sends `{event: "init"}` → frontend replies `{action: "load", xml: diagramXmlRef.current}`
4. User edits the diagram in draw.io
5. User clicks Save → draw.io sends `{event: "save", xml: ...}` → frontend posts to `/diagram/save`

### Security
Only accepts `postMessage` events from:
- `https://embed.diagrams.net`
- `https://app.diagrams.net`
- `https://www.draw.io`
- `https://draw.io`

## Generator (`diagram_generator.py`)

Creates an `mxGraphModel` XML from financial data:

- **Nodes**: Title, Goal, Income (+ Extra), Expenses, Savings (+ Debts), Calculation
- **Colors**:
  - Income nodes: green (`#00FF00`, stroke `#009900`)
  - Expense/Debt nodes: red (`#FF4444`, stroke `#CC0000`)
  - Asset/Goal nodes: blue (`#4A90D9`, stroke `#2C6FAD`)
  - Result node: purple (`#9B59B6`, stroke `#7D3C98`)
- **Layout**: Center-aligned, stacked vertically, 60px vertical gap
- **Arrows**: Directed from top to bottom between each consecutive pair
