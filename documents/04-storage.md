# Storage

Two layers: local JSON (always works) + remote API (best-effort, background).

## Local Storage

**Path:** `~/.mujarrad-chat/history.json` (falls back to system temp if unwritable)

**Format:** JSON array of `ChatRecord` objects.

Created automatically on first save. Always reads the entire file, appends, and writes the entire file.

## Remote Storage

Runs as an `asyncio.create_task` after the response is sent — never blocks the user.

Two API spaces:

### Chat History Space
- **Slug:** `chat`
- **Endpoint:** `POST {base}/spaces/chat/nodes`
- **Payload:** `{ title: "chat-{id}", nodeType: "REGULAR", nodeDetails: ChatRecord }`

### Segment Nodes Space
- **Slug:** `example`
- **Endpoint:** `POST {base}/spaces/example/nodes`
- **Purpose:** Per-turn financial data for auditing (legacy, not used by the guided `/chat`)

### API Authentication
| Header | Value |
|--------|-------|
| `X-API-Key` | Public key from `.env` |
| `X-API-Secret` | Secret key from `.env` |

## Storage Flow

```
save_chat_record(record)
  ├── Local: append to history.json (always works)
  └── Remote: POST to API (best-effort, failures logged)

get_history(user_id)
  ├── Read local history.json
  ├── GET remote API (paginated, size=50)
  │   ├── Success → replace local with remote data, return remote
  │   └── Failure → return local data
  └── Return result
```

## Configuration (`.env`)

```
MUJARRAD_PUBLIC_KEY=...
MUJARRAD_SECRET_KEY=...
MUJARRAD_SPACE_URL=https://www.mujarrad.com/spaces/chat
MUJARRAD_SEGMENTS_SPACE_URL=https://www.mujarrad.com/spaces/example
```

Space slugs are extracted from the last path segment of each URL.
