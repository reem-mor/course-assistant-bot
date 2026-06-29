"""LLM router fallback node.

Used only when the deterministic keyword router (``app.bot.router``) returns None. Calls
the router-role model with the JSON-only Section 12 prompt and parses the result
defensively. Any failure (no provider, malformed JSON, unknown intent) returns None so the
caller can degrade gracefully.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.bot.router import Intent, IntentName, Scope
from app.core.logging import get_logger
from app.graph.prompts import ROUTER_SYSTEM
from app.services.llm import ModelRole, try_get_model_registry

_log = get_logger("graph.router")

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_INTENT_MAP: dict[str, IntentName] = {
    "schedule": IntentName.SCHEDULE,
    "summarize": IntentName.SUMMARIZE,
    "recording": IntentName.RECORDING,
    "homework_latest": IntentName.HOMEWORK_LATEST,
    "homework_submit": IntentName.HOMEWORK_SUBMIT,
    "materials": IntentName.MATERIALS,
}
_SCOPE_MAP: dict[str, Scope] = {s.value: s for s in Scope}

_ROUTER_MAX_TOKENS = 200


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a model response, tolerating fences/prose."""
    match = _JSON_OBJECT_RE.search(raw)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_router_json(raw: str) -> Intent | None:
    """Parse a router JSON payload into an Intent, or None if unusable/unsupported."""
    data = _extract_json(raw)
    if data is None:
        return None
    intent_name = _INTENT_MAP.get(str(data.get("intent", "")).lower())
    if intent_name is None:
        return None
    scope_raw = data.get("scope")
    scope = _SCOPE_MAP.get(str(scope_raw).lower()) if scope_raw else None
    lesson_ref = data.get("lesson_ref")
    return Intent(
        name=intent_name,
        scope=scope,
        lesson_ref=str(lesson_ref) if lesson_ref else None,
    )


async def classify(text: str) -> Intent | None:
    """Classify a message via the router-role LLM, or None on any failure."""
    registry = try_get_model_registry()
    if registry is None:
        return None
    try:
        model = registry.for_role(ModelRole.ROUTER)
        raw = await model.complete(
            system=ROUTER_SYSTEM, prompt=text, max_tokens=_ROUTER_MAX_TOKENS
        )
    except Exception:  # never let routing crash a turn
        _log.exception("llm_router_failed")
        return None
    return parse_router_json(raw)
