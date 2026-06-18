# Storage System

The system uses two storage layers: local JSON (always) and remote Mujarrad API (best-effort).

---

## Local Storage

**Path:** `~/.mujarrad-chat/history.json`

Created automatically on first `save_chat_record()`. Falls back to system temp directory if `~` is unwritable.

**Format:** JSON array of serialized `ChatRecord` dicts.

**Operations:**
- `save_chat_record()`: Append record → write full array
- `get_history()`: Read & filter by `user_id`
- **No partial updates** — always reads entire file, appends, writes entire file

---

## Mujarrad Remote Storage

Two separate "spaces" (equivalent to collections/tables):

### 1. Chat History Space (`chat` slug)

| Field | Value |
|-------|-------|
| API | `POST {base}/spaces/chat/nodes` |
| Title | `chat-{record.id}` |
| nodeType | `REGULAR` |
| nodeDetails | Full ChatRecord dict |

**Used for:** History sidebar in frontend, persistent conversation recall.

### 2. Segment Nodes Space (`example` slug)

| Field | Value |
|-------|-------|
| API | `POST {base}/spaces/example/nodes` |
| Title | `seg-{conversation_id}-{segment_index}` |
| nodeType | `REGULAR` |
| nodeDetails | `{id, user_id, conversation_id, segment_index, text, classifications}` |

**Used for:** Per-sentence financial data analysis, auditing.

**Saved twice per message:**
1. **RAW** (before LLM): segment text without classifications
2. **CLASSIFIED** (after LLM): segment text + financial field classifications

### API Authentication

| Header | Value |
|--------|-------|
| `X-API-Key` | `pk_live_...` (public key from .env) |
| `X-API-Secret` | `sk_live_...` (secret key from .env) |

---

## Storage Flow

```
save_chat_record(record)
  ├── 1. Local: append to history.json (ALWAYS works)
  └── 2. Remote: async POST to Mujarrad /spaces/chat/nodes (best-effort)
       └── On failure: log "skipped", no retry

get_history(user_id)
  ├── 1. Local: read & filter history.json
  ├── 2. Remote: GET /spaces/chat/nodes?page=N&size=50 (paginated)
  │    ├── On success: save remote data to local, return remote data
  │    └── On failure: return local data
  └── 3. Return
```

## Why Two Spaces?

- **Chat space** = conversation records for the history UI (complete with messages, extracted data, calculation)
- **Example space** = financial segment nodes for per-sentence classification visibility (independent of conversation context)

## Configuration

Set in `.env`:
```
MUJARRAD_PUBLIC_KEY=pk_live_...
MUJARRAD_SECRET_KEY=sk_live_...
MUJARRAD_SPACE_URL=https://www.mujarrad.com/spaces/chat
MUJARRAD_SEGMENTS_SPACE_URL=https://www.mujarrad.com/spaces/example
```

Space slugs are extracted from the last path segment of their URLs.
