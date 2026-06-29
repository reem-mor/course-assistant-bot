"""lesson_map persistence (Phase 2: YAML-backed).

Behind the ``LessonMapStore`` protocol so Phase 5 can swap to a DB table without
touching callers. Admin ``/map`` edits and confirmed auto-suggestions are written back to
``data/lesson_map.yaml`` atomically.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from app.domain.lesson_map import LessonMap, LessonRoots, SessionLink

_DEFAULT_LESSON_MAP_PATH = Path(__file__).resolve().parents[2] / "data" / "lesson_map.yaml"


@runtime_checkable
class LessonMapStore(Protocol):
    """Read/write access to the lesson_map."""

    def load(self) -> LessonMap: ...

    def set_link(
        self,
        session_date: str,
        *,
        recording_alex_label: int | None,
        presentation_alex_label: int | None,
    ) -> LessonMap: ...


def _parse(data: dict[str, Any]) -> LessonMap:
    """Build a LessonMap from raw YAML data."""
    roots = LessonRoots.model_validate(data.get("roots", {}))
    raw_recordings: dict[Any, Any] = data.get("recordings_by_alex_label") or {}
    recordings = {int(k): str(v) for k, v in raw_recordings.items()}
    raw_links: dict[Any, Any] = data.get("session_links") or {}
    links = {
        str(date): SessionLink.model_validate(payload or {})
        for date, payload in raw_links.items()
    }
    return LessonMap(roots=roots, recordings_by_alex_label=recordings, session_links=links)


def _dump(lesson_map: LessonMap) -> str:
    """Serialize a LessonMap back to the YAML on-disk shape."""
    payload: dict[str, object] = {
        "roots": lesson_map.roots.model_dump(),
        "recordings_by_alex_label": dict(sorted(lesson_map.recordings_by_alex_label.items())),
        "session_links": {
            date: link.model_dump(exclude_none=True)
            for date, link in sorted(lesson_map.session_links.items())
        },
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


class YamlLessonMapStore:
    """``LessonMapStore`` backed by a YAML file with atomic writes."""

    def __init__(self, path: Path | str = _DEFAULT_LESSON_MAP_PATH) -> None:
        self._path = Path(path)

    def load(self) -> LessonMap:
        """Load and validate the lesson_map from disk."""
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return _parse(dict(data))

    def save(self, lesson_map: LessonMap) -> None:
        """Persist a LessonMap atomically (temp file + replace)."""
        text = _dump(lesson_map)
        directory = self._path.parent
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self._path)

    def set_link(
        self,
        session_date: str,
        *,
        recording_alex_label: int | None,
        presentation_alex_label: int | None,
    ) -> LessonMap:
        """Set (or update) a session link and persist, returning the updated map."""
        lesson_map = self.load()
        links = dict(lesson_map.session_links)
        links[session_date] = SessionLink(
            recording_alex_label=recording_alex_label,
            presentation_alex_label=presentation_alex_label,
        )
        updated = lesson_map.model_copy(update={"session_links": links})
        self.save(updated)
        return updated
