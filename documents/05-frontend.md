# Frontend

React 19 + Vite (port 5173, proxy → 8001). No router. No CSS framework.

## App State

| Variable | Type | Purpose |
|----------|------|---------|
| `userId` | string | `crypto.randomUUID()` persisted in localStorage |
| `conversationId` | string? | Active conversation (null = new) |
| `messages` | array | Current conversation messages |
| `history` | array | Past conversations from `/history` |
| `historyOpen` | bool | Sidebar visibility |
| `loading` | bool | Request in progress |
| `pendingYesNo` | object? | Yes/No prompt: `{ field, text, waitingValue? }` |
| `pendingAskValue` | object? | Value input prompt: `{ field, text }` |
| `askValueInput` | string | Input for `ask_value` questions |
| `yesValueInput` | string | Input for Yes-then-value |
| `diagramOpen` | bool | Diagram modal visibility |
| `diagramLoading` | bool | iframe spinner state |
| `confirmDeleteId` | string? | Conversation pending deletion confirm |
| `abortRef` | ref | `AbortController` for cancel |
| `diagramXmlRef` | ref | Current XML (survives re-renders for postMessage) |

## Chat Flow

1. **User types** → `sendChat(text)` — creates optimistic user message, POST `/chat`
2. **Response handling**:
   - `is_complete: true` → show assistant text + analysis grid + result panel + "View Financial Plan" button
   - `question_type: "yesno"` → show Yes/No buttons; Yes opens inline value input
   - `question_type: "ask_value"` → show inline number input
   - `question_type: "restore_context"` → Yes restores previous session, No starts fresh
3. **Cancel** → `cancelRequest()` calls `abortRef.current.abort()`, clears loading

### Analysis Grid
Rendered inside `Message` when `extracted_data` exists with `is_complete`. Shows up to 7 `Metric` rows (Goal, Income, Expenses, Savings, Debts, Net Savings, Extra). Null fields hidden. 5-column grid on desktop → 2 columns ≤860px.

### Metric Component
Returns `null` for `null`/`undefined` values. Formats with `Intl.NumberFormat` (0 decimals).

## History Sidebar

- Toggled by hamburger icon in top bar
- Groups conversations by `conversation_id` (deduped via `useMemo`), sorted by latest message
- Each entry shows first user message as title
- **Long-press (200ms)** or **right-click** reveals delete confirmation
- Click to restore conversation (rebuilds messages + pending prompts from last state)

## Diagram Modal (Draw.io Integration)

1. User clicks "View Financial Plan" → POST `/diagram` → store XML → open iframe
2. Load `https://embed.diagrams.net?embed=1&ui=dark&save=1&proto=json`
3. **postMessage protocol**:
   - `init` from draw.io → reply `{ action: "load", xml: diagramXmlRef.current }`
   - `load` from draw.io → hide spinner
   - `save` from draw.io → POST `/diagram/save` with XML
4. Strict origin validation: only `*.diagrams.net`, `*.draw.io`
5. Full-screen on mobile (≤860px), 90vw×90vh on desktop

## Styling

| Variable | Value |
|----------|-------|
| `--bg` | `#070511` |
| `--bg-2` | `#12082A` |
| `--primary` | `#8E3DFF` |
| `--accent` | `#B56CFF` |
| `--text` | `#F3EEFF` |
| `--text-muted` | `#C9A4FF` |

Yes/No buttons: green-tinted (Yes), red-tinted (No). Dark semi-transparent bubbles with purple border/glow. Responsive breakpoint at 860px.
