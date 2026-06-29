"""Schedule re-scrape (feature 6.1).

Fetches the read-only Lovable course site with a headless browser (Playwright, lazy +
optional), parses the rendered timeline text into sessions, and diffs them against the
seeded ``schedule.yaml``. The diff is surfaced to admins; manual overrides are never
overwritten. The parser is pure text and unit-tested against a saved fixture - no live
fetch in the suite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.domain.models import Session, SessionType

_log = get_logger("schedule_scraper")

_TIMELINE_START = "ציר הזמן של המסע"
_TIMELINE_END = "אבני הדרך של המסע"

_WEEKDAY_HE = {
    "ראשון": "Sun",
    "שני": "Mon",
    "שלישי": "Tue",
    "רביעי": "Wed",
    "חמישי": "Thu",
    "שישי": "Fri",
    "שבת": "Sat",
}
_TYPE_HE: dict[str, SessionType] = {
    "טכני": SessionType.TECHNICAL,
    "סדנה / רכות": SessionType.WORKSHOP,
    "אבן דרך": SessionType.MILESTONE,
    "חג": SessionType.HOLIDAY,
}
_STATUS_WORDS = {"בוצע", "עכשיו במסע", "השבוע", "בהמשך", "חופש / חג", "משימה הבאה"}

_DAY_RE = re.compile(r"^(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)\s*·\s*(\d{2})\.(\d{2})$")
_TIME_RE = re.compile(r"^(\d{2}:\d{2})\s*[–-]\s*(\d{2}\s*:?\s*\d{2})$")
_WEEK_RE = re.compile(r"^שבוע\s+\d+")
_HOURS_RE = re.compile(r"ש׳ אקדמיות")
_SESSIONS_COUNT_RE = re.compile(r"^\d+\s+מפגשים")


@dataclass(frozen=True)
class ScrapedSession:
    """A session parsed from the live site (date as ISO ``YYYY-MM-DD``)."""

    date: str
    day: str
    time: str
    title: str
    instructor: str
    type: SessionType


@dataclass
class ScheduleDiff:
    """Differences between the scraped site and the seeded schedule."""

    added: list[ScrapedSession] = field(default_factory=list)
    changed: list[tuple[str, str]] = field(default_factory=list)  # (date, description)
    removed: list[str] = field(default_factory=list)  # dates present locally, not scraped

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.changed or self.removed)


def _is_meta(line: str) -> bool:
    """True if a line is structural noise (status/type/hours/week/count)."""
    return (
        line in _STATUS_WORDS
        or line in _TYPE_HE
        or bool(_HOURS_RE.search(line))
        or bool(_WEEK_RE.match(line))
        or bool(_SESSIONS_COUNT_RE.match(line))
        or line.isdigit()
    )


def _iso_date(day: str, month: str, *, base_year: int) -> str:
    """Map a DD.MM token to ISO date, inferring the year from the course window."""
    month_i = int(month)
    year = base_year if month_i >= 4 else base_year + 1
    return f"{year:04d}-{month_i:02d}-{int(day):02d}"


def parse_schedule_text(text: str, *, base_year: int = 2026) -> list[ScrapedSession]:
    """Parse the rendered timeline text into sessions (tolerant, best-effort)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if _TIMELINE_START in lines:
        start = lines.index(_TIMELINE_START)
        lines = lines[start + 1 :]
    if _TIMELINE_END in lines:
        lines = lines[: lines.index(_TIMELINE_END)]

    sessions: list[ScrapedSession] = []
    current_type = SessionType.TECHNICAL
    last_title: str | None = None

    i = 0
    while i < len(lines):
        line = lines[i]
        if line in _TYPE_HE:
            current_type = _TYPE_HE[line]
            i += 1
            continue
        day_match = _DAY_RE.match(line)
        if day_match and last_title is not None:
            time_str = ""
            instructor = ""
            if i + 1 < len(lines):
                time_match = _TIME_RE.match(lines[i + 1])
                if time_match:
                    time_str = f"{time_match.group(1)} - {time_match.group(2).replace(' ', '')}"
                    nxt = lines[i + 2] if i + 2 < len(lines) else ""
                    if nxt and not _is_meta(nxt) and not _DAY_RE.match(nxt):
                        instructor = nxt
            sessions.append(
                ScrapedSession(
                    date=_iso_date(day_match.group(2), day_match.group(3), base_year=base_year),
                    day=_WEEKDAY_HE.get(line.split("·")[0].strip(), ""),
                    time=time_str,
                    title=last_title,
                    instructor="" if instructor in _STATUS_WORDS else instructor,
                    type=current_type,
                )
            )
            last_title = None
            i += 1
            continue
        if not _is_meta(line) and not _TIME_RE.match(line):
            last_title = line
        i += 1
    return sessions


def diff_schedule(
    scraped: list[ScrapedSession], current: list[Session]
) -> ScheduleDiff:
    """Diff scraped sessions against the seeded schedule, keyed by ISO date."""
    by_date_current = {s.date.isoformat(): s for s in current}
    by_date_scraped = {s.date: s for s in scraped}
    diff = ScheduleDiff()
    for date, scr in by_date_scraped.items():
        cur = by_date_current.get(date)
        if cur is None:
            diff.added.append(scr)
        elif scr.title.strip() != cur.title.strip():
            diff.changed.append((date, f"'{cur.title}' -> '{scr.title}'"))
    for date in by_date_current:
        if date not in by_date_scraped:
            diff.removed.append(date)
    return diff


async def scrape_sessions(url: str) -> list[ScrapedSession]:
    """Fetch the live site with Playwright and parse its sessions (lazy import)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # optional dependency
        raise RuntimeError(
            "Playwright is not installed. Run: uv sync --extra scrape, "
            "then: playwright install chromium"
        ) from exc

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            text = await page.evaluate(
                "() => (document.querySelector('main') || document.body).innerText"
            )
        finally:
            await browser.close()
    return parse_schedule_text(text)
