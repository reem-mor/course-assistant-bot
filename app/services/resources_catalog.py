"""Curated resources catalog (feature 6.3, part 1).

Loads ``data/resources.yaml`` and matches a free-text topic to a curated topic by key or
alias (case-insensitive substring match), returning the curated links.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_DEFAULT_RESOURCES_PATH = Path(__file__).resolve().parents[2] / "data" / "resources.yaml"


@dataclass(frozen=True)
class CuratedResource:
    """A curated external resource."""

    title: str
    url: str


@dataclass(frozen=True)
class CuratedTopic:
    """A curated topic with its aliases and resources."""

    key: str
    aliases: tuple[str, ...]
    resources: tuple[CuratedResource, ...]

    def matches(self, query: str) -> bool:
        """True if the (lowercased) query matches this topic's key or any alias."""
        haystack = [self.key, *self.aliases]
        return any(term in query or query in term for term in haystack)


class ResourcesCatalog:
    """An in-memory catalog of curated topics."""

    def __init__(self, topics: list[CuratedTopic]) -> None:
        self._topics = topics

    @classmethod
    def from_yaml(cls, path: Path | str = _DEFAULT_RESOURCES_PATH) -> ResourcesCatalog:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        topics: list[CuratedTopic] = []
        for key, payload in (data.get("topics") or {}).items():
            aliases = tuple(str(a).lower() for a in (payload.get("aliases") or []))
            resources = tuple(
                CuratedResource(title=str(r["title"]), url=str(r["url"]))
                for r in (payload.get("resources") or [])
            )
            topics.append(
                CuratedTopic(key=str(key).lower(), aliases=aliases, resources=resources)
            )
        return cls(topics)

    def lookup(self, topic: str) -> list[CuratedResource]:
        """Return curated resources for the best-matching topic, or empty if none."""
        query = topic.strip().lower()
        if not query:
            return []
        for curated in self._topics:
            if curated.matches(query):
                return list(curated.resources)
        return []


@lru_cache(maxsize=1)
def get_resources_catalog() -> ResourcesCatalog:
    """Return a cached catalog loaded from the default path."""
    return ResourcesCatalog.from_yaml()
