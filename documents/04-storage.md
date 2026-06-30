# Storage

Dual persistence: local JSON (always works) + remote Mujarrad API (best-effort, background).

## Local Storage

**Path**: `~/.mujarrad-chat/history.json` (falls back to system temp if unwritable)
**Format**: JSON array of `ChatRecord` objects.
Reads entire file, appends, writes entire file. No partial writes.

## Remote Storage Spaces

| Slug | Space URL | Content |
|------|-----------|---------|
| `chat` | `/spaces/chat` | Chat records (history) |
| `example` | `/spaces/example` | Segment nodes (legacy) |

Slugs extracted from URL path in config via `space_url.split("/")[-1]`.

## Methods (`MujarradStorage`)

| Method | Type | Space | Notes |
|--------|------|-------|-------|
| `save_chat_record(record)` | POST | chat | Local + remote |
| `save_context_node(context)` | POST | configurable | Remote only |
| `get_context_node(conv_id, user_id)` | GET | configurable | Remote only |
| `save_segment_node(data, ...)` | POST | example | Legacy, remote only |
| `save_diagram_node(conv_id, user_id, xml)` | POST | chat | Remote only |
| `get_diagram_node(conv_id, user_id)` | GET | chat | Returns XML string |
| `get_history(user_id)` | GET | chat | Local first → remote (paginated 50/size) → merge |
| `delete_history(conv_id, user_id)` | DELETE | chat | Local delete + remote DELETE |
| `check_connection()` | GET | chat | Minimal health check |

## History Merge Strategy

1. Load local `history.json`
2. Fetch remote records (paginated, 50/page)
3. Local records are primary — remote items only supplement if `conversation_id` not seen locally
4. If remote fetch succeeds → replace local with merged result
5. If remote fetch fails → return local data

## Backup Strategy

All remote saves are `asyncio.create_task` — exceptions logged, never raised. Local save always runs first. If remote fails, data is preserved locally.

## Auth

| Header | Value |
|--------|-------|
| `X-API-Key` | `mujarrad_public_key` |
| `X-API-Secret` | `mujarrad_secret_key` |

## Config (.env)

```
MUJARRAD_PUBLIC_KEY=...
MUJARRAD_SECRET_KEY=...
MUJARRAD_API_BASE=https://www.mujarrad.com/api
MUJARRAD_SPACE_URL=https://www.mujarrad.com/spaces/chat
MUJARRAD_SEGMENTS_SPACE_URL=https://www.mujarrad.com/spaces/example
MUJARRAD_GRAPH_SPACE_URL=https://www.mujarrad.com/spaces/graph
```
