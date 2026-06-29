"""Write access to ``data/schedule.yaml`` for admin schedule overrides (6.10).

Manual edits are stamped ``manual: true`` so the weekly re-scrape proposes website changes
rather than overwriting them. Writes are atomic.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_SCHEDULE_PATH = Path(__file__).resolve().parents[2] / "data" / "schedule.yaml"

_ALLOWED_FIELDS = {"day", "time", "title", "instructor", "type", "week", "status"}


class ScheduleStore:
    """Loads and persists the schedule YAML, supporting manual session upserts."""

    def __init__(self, path: Path | str = _DEFAULT_SCHEDULE_PATH) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, Any]:
        return yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}

    def _save(self, data: dict[str, Any]) -> None:
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self._path.parent, delete=False, suffix=".tmp"
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self._path)

    def upsert_session(self, date: str, fields: dict[str, str]) -> str:
        """Add or update a session by ISO date, marking it a manual override.

        Returns "added" or "updated". Only known fields are written.
        """
        clean = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
        data = self._load()
        sessions: list[dict[str, Any]] = list(data.get("sessions") or [])
        for entry in sessions:
            if str(entry.get("date")) == date:
                entry.update(clean)
                entry["manual"] = True
                data["sessions"] = sessions
                self._save(data)
                return "updated"
        new_entry: dict[str, Any] = {"date": date, "manual": True, **clean}
        sessions.append(new_entry)
        data["sessions"] = sessions
        self._save(data)
        return "added"

    def cancel_session(self, date: str) -> bool:
        """Mark a session cancelled (status=cancelled, manual). Returns True if found."""
        data = self._load()
        sessions = list(data.get("sessions") or [])
        for entry in sessions:
            if str(entry.get("date")) == date:
                entry["status"] = "cancelled"
                entry["manual"] = True
                data["sessions"] = sessions
                self._save(data)
                return True
        return False
