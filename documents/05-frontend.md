# Frontend

React 19 application using Vite, no router, no state management library — just hooks.

## Components

### `App` (root)
**State:**
| Variable | Type | Purpose |
|----------|------|---------|
| `userId` | string | Current user |
| `conversationId` | string? | Active conversation (null = new) |
| `messages` | array | Chat messages for active conversation |
| `input` | string | Text input |
| `history` | array | Past conversations |
| `loading` | bool | Waiting for backend |
| `pendingYesNo` | object? | Current yes/no question: `{ field, text }` |
| `abortRef` | ref | `AbortController` for cancel |

### `Message` (child)
Renders a single chat bubble. If the message contains `extracted_data` and `calculation`, shows:
- **Analysis grid**: income, expenses, net savings (with debt indicator if applicable)
- **Result panel**: timeline duration, achievability, suggestions
- **"View Financial Plan" button**: opens the diagram modal (see 07-diagram.md)

If `extracted_data` exists but `is_complete` is false, only the text is shown (no grid).

### `Metric` (child)
Displays a labeled value row. Returns `null` for `null`/`undefined` values — unmentioned fields are invisible.

## Chat Flow

### Send Message
1. Create `AbortController` for cancellation
2. POST `/chat` with message, userId, conversationId
3. If `is_complete: false`:
   - Show assistant message text
   - Show Yes/No buttons
   - On Yes: show inline input for the value
   - On No: automatically send "No" as next message
4. If `is_complete: true`:
   - Show assistant message + analysis grid + result
   - Hide Yes/No buttons
5. On error or abort: show error state, re-enable input

### Cancel
Shows a cancel button during `loading`. Clicking it aborts the fetch via `AbortController`.

## History Sidebar
- Groups conversations by `conversation_id`
- Most recent first
- Each entry shows the first user message as the title
- Click to resume a past conversation
- GET `/history` on page load

## Styling
| Variable | Value |
|----------|-------|
| `--bg` | `#02000F` |
| `--primary` | `#541288` |
| `--accent` | `#A582B1` |
| `--text` | `#F5F5F5` |

- Dark theme via CSS variables
- Responsive breakpoint at 860px
- No CSS framework — all custom

## Diagram Modal
- Embedded iframe loading `https://embed.diagrams.net`
- Cross-origin messaging: `postMessage` API
- Only accepts messages from `*.diagrams.net`, `*.draw.io`
- Save button in draw.io triggers a POST to `/diagram/save`
