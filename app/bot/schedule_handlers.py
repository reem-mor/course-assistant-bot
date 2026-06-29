"""Schedule feature handlers and formatting (feature 6.1).

Formats typed ``Session`` objects into localized he/en replies. Pure formatting helpers
are separated from the Telegram handler so they can be unit-tested without a bot.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from app.bot.router import Intent, IntentName, Scope
from app.core.i18n import Language, detect_language, t
from app.core.logging import get_logger
from app.domain.models import Session, SessionType
from app.services.schedule import (
    YamlScheduleService,
    get_schedule_service,
    week_window,
)

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

_log = get_logger("bot.schedule")

_TYPE_LABEL_KEY: dict[SessionType, str] = {
    SessionType.TECHNICAL: "type_technical",
    SessionType.WORKSHOP: "type_workshop",
    SessionType.MILESTONE: "type_milestone",
    SessionType.HOLIDAY: "type_holiday",
}


def _fmt_date(value: date) -> str:
    """Format a date as DD/MM/YYYY (consistent with the course conventions)."""
    return value.strftime("%d/%m/%Y")


def _day_label(day: str, language: Language) -> str:
    """Localize a 3-letter weekday code (e.g. 'Wed') to a full weekday name."""
    return t(f"day_{day}", language)


def _format_session(session: Session, language: Language) -> str:
    """Render a single session as a localized multi-line block."""
    lines = [
        session.title,
        f"{_day_label(session.day, language)}, {_fmt_date(session.date)} · {session.time}",
    ]
    if session.has_named_instructor:
        lines.append(f"{t('label_instructor', language)}: {session.instructor}")
    type_label = t(_TYPE_LABEL_KEY[session.type], language)
    lines.append(f"{t('label_type', language)}: {type_label}")
    if not session.is_technical:
        lines.append(t("sched_nontechnical_note", language))
    return "\n".join(lines)


def format_next(service: YamlScheduleService, language: Language) -> str:
    """Format the 'next lesson' reply, handling course-finished."""
    session = service.next_session()
    if session is None:
        return t("sched_course_finished", language)
    parts = [t("sched_next_header", language), "", _format_session(session, language)]
    if service.is_holiday_today():
        parts.append("")
        parts.append(t("sched_holiday_today", language))
    return "\n".join(parts)


def format_this_week(service: YamlScheduleService, language: Language) -> str:
    """Format the 'this week' reply, handling an empty week."""
    start, end = week_window(service.today())
    header = t("sched_week_header", language).format(
        start=_fmt_date(start), end=_fmt_date(end)
    )
    sessions = service.sessions_this_week()
    if not sessions:
        return f"{header}\n{t('sched_week_empty', language)}"
    blocks = [_format_session(s, language) for s in sessions]
    return header + "\n\n" + "\n\n".join(blocks)


def format_full(service: YamlScheduleService, language: Language) -> str:
    """Format the full schedule grouped by week."""
    parts = [t("sched_full_header", language)]
    for week_no, sessions in service.sessions_grouped_by_week():
        parts.append("")
        parts.append(t("sched_week_group", language).format(n=week_no))
        for session in sessions:
            parts.append(_format_session(session, language))
            parts.append("")
    return "\n".join(parts).rstrip()


def render_schedule(service: YamlScheduleService, intent: Intent, language: Language) -> str:
    """Dispatch a schedule intent to the matching formatter."""
    if intent.scope is Scope.NEXT:
        return format_next(service, language)
    if intent.scope is Scope.THIS_WEEK:
        return format_this_week(service, language)
    return format_full(service, language)


def reply_for_intent(intent: Intent, language: Language) -> str | None:
    """Produce a reply string for a routed intent, or None if unhandled here.

    Phase 1 handles only the schedule intent; other intents fall through.
    """
    if intent.name is not IntentName.SCHEDULE:
        return None
    return render_schedule(get_schedule_service(), intent, language)


async def schedule_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/schedule``: reply with the full course schedule."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    _log.info("schedule_command", language=language)
    await message.reply_text(format_full(get_schedule_service(), language))
