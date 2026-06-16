import json
import os
from pathlib import Path
from typing import Any

import httpx
from .config import get_settings
from .models import ChatRecord


API_TIMEOUT = 15
DATA_DIR = Path(os.path.expanduser("~")) / ".mujarrad-chat"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_DB = DATA_DIR / "history.json"


class MujarradStorage:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.mujarrad_api_base.rstrip("/")
        self.slug = self.settings.mujarrad_space_slug
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.settings.mujarrad_public_key,
            "X-API-Secret": self.settings.mujarrad_secret_key,
        }

    # ── Local fallback (JSON file) ──────────────────────────────

    def _load_local(self) -> list[dict[str, Any]]:
        if not LOCAL_DB.exists():
            return []
        try:
            return json.loads(LOCAL_DB.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_local(self, records: list[dict[str, Any]]) -> None:
        LOCAL_DB.write_text(json.dumps(records, ensure_ascii=False, default=str), encoding="utf-8")

    # ── Public API ──────────────────────────────────────────────

    async def save_chat_record(self, record: ChatRecord) -> None:
        data = record.model_dump()

        # Local save (always works)
        local = self._load_local()
        local.append(data)
        self._save_local(local)

        # Remote save (Mujarrad)
        payload = {
            "title": f"chat-{record.conversation_id}",
            "nodeType": "REGULAR",
            "nodeDetails": data,
        }
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/spaces/{self.slug}/nodes",
                    json=payload,
                    headers=self.headers,
                )
                print("Mujarrad POST:", response.status_code, response.text)
                response.raise_for_status()
        except Exception as e:
            print("Mujarrad remote save skipped:", e)

    async def get_history(self, user_id: str) -> list[dict[str, Any]]:
        local = self._load_local()
        records = [r for r in local if r.get("user_id") == user_id]

        # Try remote to get fresher data
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(
                    f"{self.base_url}/spaces/{self.slug}/nodes",
                    headers=self.headers,
                )
                if response.is_success:
                    data = response.json()
                    nodes = data.get("content", []) if isinstance(data, dict) else []
                    if isinstance(nodes, list):
                        remote = []
                        for node in nodes:
                            details = node.get("nodeDetails") or {}
                            if details.get("user_id") == user_id:
                                remote.append(details)
                        if remote:
                            self._save_local(remote)
                            return remote
        except Exception as e:
            print("Mujarrad remote fetch skipped:", e)

        return records

    async def check_connection(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(
                    f"{self.base_url}/spaces/{self.slug}/nodes?size=1",
                    headers=self.headers,
                )
                if response.status_code == 401:
                    return {"connected": False, "error": "Invalid API keys"}
                response.raise_for_status()
                return {"connected": True, "space": self.slug, "api": self.base_url}
        except httpx.ConnectError:
            return {"connected": False, "error": f"Cannot reach {self.base_url}"}
        except Exception as e:
            return {"connected": False, "error": str(e)}