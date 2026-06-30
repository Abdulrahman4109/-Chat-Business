# Financial Roadmap Diagram

Draw.io (`mxGraphModel` XML) generation for the financial goal timeline.

## Generator (`diagram_generator.py`)

**Trigger**: User clicks "View Financial Plan" after calculation complete.
**Input**: `FinancialData` + `CalculationResult`
**Output**: Two-row layout, 1100×850 canvas, dark theme background `#070511`.

### Row 1 (Y=45): Cash Flow
```
[Income: +$15K] → [Expenses: -$4.2K] → [Net Savings: =$10.8K]
```
- Income: purple `#8E3DFF` with `+` prefix
- Expenses: pink `#E35CFF` with `-` prefix
- Extra Income (if >0): purple `#8E3DFF`
- Net Savings: pink if negative, light purple `#B56CFF` if positive

### Row 2 (Y=195): Goal Progress
```
[Savings: $200K] → [Goal: $800K] → [Still Needed: $650K] → [Timeline: 5y 1mo]
```
- Savings: light purple `#C9A4FF`
- Debts (if >0): pink `#E35CFF` (connected between Savings → Goal)
- Goal: purple `#8E3DFF`
- Still Needed: pink if >0, light purple if 0
- Timeline: green `#27AE60` if achievable, pink if not

### Connecting edge
From Net Savings (row 1) down to Still Needed (row 2) — shows where monthly savings go.

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/diagram` | Generate from FinancialData + CalculationResult |
| POST | `/diagram/save` | Save edited XML |
| GET | `/diagram/load` | Load saved XML |

## Frontend Integration

The draw.io modal pattern:
1. iframe → `https://embed.diagrams.net?embed=1&ui=dark&save=1&proto=json`
2. `postMessage` protocol: init → load XML, save → persist
3. Origin whitelist: `*.diagrams.net`, `*.draw.io`
4. XML held in ref (`diagramXmlRef`) to survive re-renders
