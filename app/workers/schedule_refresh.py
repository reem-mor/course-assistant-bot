"""Weekly schedule re-scrape job (feature 6.1).

Scrapes the live course site, diffs it against the seeded ``schedule.yaml``, and notifies
owners with the diff. It never overwrites the local schedule - admins apply changes via
``/schedule_update`` (manual overrides win).
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.core.settings import Settings
from app.services.schedule import YamlScheduleService
from app.services.schedule_scraper import ScheduleDiff, diff_schedule, scrape_sessions

_log = get_logger("worker.schedule_refresh")


def format_diff(diff: ScheduleDiff) -> str:
    """Render a schedule diff as a short admin-facing summary."""
    if not diff.has_changes:
        return "Schedule re-scrape: no changes detected."
    lines = ["Schedule re-scrape found changes:"]
    for session in diff.added:
        lines.append(f"+ added {session.date}: {session.title}")
    for date, desc in diff.changed:
        lines.append(f"~ changed {date}: {desc}")
    for date in diff.removed:
        lines.append(f"- not on site {date}")
    lines.append("\nApply with /schedule_update (manual overrides are kept).")
    return "\n".join(lines)


class ScheduleRefresher:
    """Scrapes the site and notifies owners of any diff vs the seeded schedule."""

    def __init__(self, schedule: YamlScheduleService, bot: Any, settings: Settings) -> None:
        self._schedule = schedule
        self._bot = bot
        self._settings = settings

    async def run_once(self) -> ScheduleDiff:
        """Scrape, diff, and notify owners. Returns the diff (empty on failure)."""
        try:
            scraped = await scrape_sessions(self._settings.course_website_url)
        except Exception:  # scraping is best-effort; never crash the scheduler
            _log.exception("schedule_scrape_failed")
            return ScheduleDiff()
        diff = diff_schedule(scraped, self._schedule.all_sessions())
        if diff.has_changes and self._bot is not None:
            summary = format_diff(diff)
            for owner_id in self._settings.owner_telegram_ids:
                try:
                    await self._bot.send_message(chat_id=owner_id, text=summary)
                except Exception:
                    _log.exception("schedule_notify_failed", owner_id=owner_id)
        _log.info("schedule_refresh", changes=diff.has_changes)
        return diff
