# Frontend

React 19 + Vite single-page application with dark theme.

---

## Components

### `App` (root — `main.jsx`)

**State:**
| Variable | Type | Source | Description |
|----------|------|--------|-------------|
| `userId` | string | localStorage | Persistent user ID (generated once) |
| `conversationId` | string? | Server response | Links messages in a conversation |
| `messages[]` | ChatMessage[] | Local state + API | Message history for current conversation |
| `input` | string | Textarea | Current input text |
| `history[]` | ChatRecord[] | GET /history | All past conversations |
| `loading` | boolean | | Loading indicator |
| `sidebarOpen` | boolean | | Mobile sidebar toggle |

**Key Handlers:**
- `sendMessage()` → POST /chat with message + userId + conversationId
- `loadHistory()` → GET /history?user_id=
- Sidebar "New goal" → resets conversationId, shows welcome message
- Sidebar history item → rebuilds messages from saved ChatRecords

### `Message` (chat bubble — `main.jsx`)

Renders a chat bubble containing:
1. **Text content** (`.bubble p`)
2. **Analysis grid** (`.analysisGrid`) — if `message.extracted_data` exists:
   - Goal, Income, Expenses, Savings, Extra — each as a `Metric` component
3. **Result panel** (`.resultPanel`) — if `message.calculation` exists:
   - Duration display (e.g., "3 years and 5 months")
   - Net monthly savings
   - Remaining amount

### `Metric` (label+value card)

Simple display component: label (e.g., "Goal") + formatted number (e.g., "800,000").

---

## API Integration

All API calls go through `API_BASE_URL` (from `VITE_API_BASE_URL` env var, or `''` for same-origin).

In development, Vite proxies:
```
/chat     → http://localhost:8001
/history  → http://localhost:8001
/health   → http://localhost:8001
/analyze  → http://localhost:8001
/calculate→ http://localhost:8001
/mujarrad → http://localhost:8001
```

**Why 8001 not 8000?** The Vite dev server runs on 5173 and proxies to 8001. The backend can run on either — the proxy configuration targets 8001.

---

## Styling

### Color Palette (CSS Variables)
| Variable | Value | Usage |
|----------|-------|-------|
| `--bg` | `#02000F` | Main background |
| `--bg-2` | `#210A41` | Sidebar, composer |
| `--primary` | `#541288` | Buttons, user bubbles |
| `--accent` | `#A582B1` | Subtle text, borders |
| `--text` | `#f4eff8` | Primary text |
| `--text-muted` | `#595063` | Placeholder text |

### Layout
- Desktop: CSS Grid — sidebar (304px) + main (1fr)
- Mobile (≤860px): sidebar overlays as slide-in drawer

### Breakpoints
- `860px`: Grid → single column, sidebar becomes overlay
- Analysis grid: 5 columns desktop → 2 columns mobile

---

## Conversation Grouping

History is grouped by `conversation_id`, sorted by `created_at` (most recent first). Sidebar shows the first user message as a label.

When a history item is clicked:
1. The saved ChatRecord pair (user_message + assistant_message) is rebuilt into the messages array
2. The conversation_id is restored
3. The user can continue the conversation
