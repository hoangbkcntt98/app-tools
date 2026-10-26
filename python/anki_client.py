"""Small AnkiConnect HTTP client used by the CLI."""
from __future__ import annotations

from typing import Any

import requests


class AnkiConnector:
    def __init__(self, api_url: str = "http://127.0.0.1:8765", timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        if not self.api_url.endswith("/api"):
            self.api_url += "/api"
        self.timeout = timeout

    def _invoke(self, action: str, params: dict[str, Any] | None = None, *, timeout: int | None = None) -> Any:
        response = requests.post(
            self.api_url,
            json={"action": action, "version": 6, "params": params or {}},
            timeout=self.timeout if timeout is None else timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"AnkiConnect {action} failed: {payload['error']}")
        return payload.get("result")

    def list_notes(self, query: str = "", limit: int | None = None) -> list[dict[str, Any]]:
        note_ids = self._invoke("findNotes", {"query": query})
        if limit is not None:
            note_ids = note_ids[:limit]
        if not note_ids:
            return []
        return self._invoke("notesInfo", {"notes": note_ids})

    def sync(self, timeout: int = 300) -> Any:
        return self._invoke("sync", timeout=timeout)

    def add_note(
        self,
        deck: str,
        note_type: str,
        fields: dict[str, str],
        tags: list[str] | None = None,
    ) -> Any:
        return self._invoke(
            "addNote",
            {
                "note": {
                    "deckName": deck,
                    "modelName": note_type,
                    "fields": fields,
                    "tags": tags or [],
                }
            },
        )

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> Any:
        return self._invoke("updateNoteFields", {"note": note_id, "fields": fields})

    def delete_notes(self, note_ids: list[int]) -> Any:
        return self._invoke("deleteNotes", {"notes": note_ids})
