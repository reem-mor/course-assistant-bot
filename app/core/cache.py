"""Small caching helpers.

A thin wrapper over ``cachetools`` TTL caches plus a content-hash helper, used for
summaries and transcripts (keyed by content hash / modifiedTime) per the latency section.
"""

from __future__ import annotations

import hashlib

from cachetools import TTLCache

# One day default TTL; summaries/transcripts are also keyed by content hash so staleness
# is bounded by content changes, not just time.
DEFAULT_TTL_SECONDS = 24 * 60 * 60


def content_hash(*parts: str) -> str:
    """Return a stable short hash for the given string parts."""
    digest = hashlib.sha256("\u0000".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def make_ttl_cache(maxsize: int = 256, ttl: int = DEFAULT_TTL_SECONDS) -> TTLCache[str, str]:
    """Create a string-keyed, string-valued TTL cache."""
    return TTLCache(maxsize=maxsize, ttl=ttl)
