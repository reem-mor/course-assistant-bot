"""Admin announcements and schedule overrides (feature 6.10).

``/announce`` broadcasts a free-text message to all subscribers (preview -> Send/Cancel),
reusing the throttled, idempotent notifier. ``/schedule_update`` applies a manual schedule
override (stamped so the re-scrape won't clobber it). Both are admin-gated.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.admin_handlers import has_admin_access
from app.core.i18n import detect_language, t
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.repo.db import get_sessionmaker
from app.repo.repositories import BroadcastLogRepo, SubscriberRepo
from app.services.notifier import Notifier, TelegramNotifier
from app.services.schedule_store import ScheduleStore

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

_log = get_logger("bot.announce")

_PENDING_KEY = "pending_announcement"


def _notifier(bot: Any) -> Notifier:
    sm = get_sessionmaker()
    return TelegramNotifier(
        bot, SubscriberRepo(sm), BroadcastLogRepo(sm),
        rate_per_sec=get_settings().broadcast_rate_per_sec,
    )


def _store() -> ScheduleStore:
    return ScheduleStore()


async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin ``/announce <text>``: preview then send to all subscribers."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    if not await has_admin_access(update):
        await message.reply_text(t("admin_refused", language))
        return
    text = " ".join(getattr(context, "args", None) or []).strip()
    if not text:
        await message.reply_text(t("announce_usage", language))
        return
    context.user_data[_PENDING_KEY] = text  # type: ignore[index]
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("announce_btn_send", language), callback_data="ann:send"
                ),
                InlineKeyboardButton(
                    t("announce_btn_cancel", language), callback_data="ann:cancel"
                ),
            ]
        ]
    )
    await message.reply_text(
        t("announce_preview", language).format(text=text), reply_markup=keyboard
    )


async def announce_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the announcement Send/Cancel buttons."""
    query = update.callback_query
    message = update.effective_message
    if query is None or message is None:
        return
    await query.answer()
    language = detect_language(message.text)
    if not await has_admin_access(update):
        await message.reply_text(t("admin_refused", language))
        return
    action = (query.data or "").split(":", 1)[-1]
    data: dict[str, Any] = context.user_data  # type: ignore[assignment]
    text = data.pop(_PENDING_KEY, None)
    if action == "cancel" or not text:
        await message.reply_text(t("announce_cancelled", language))
        return
    result = await _notifier(context.bot).broadcast(
        idempotency_key=f"announce:{uuid.uuid4()}", message=text
    )
    await message.reply_text(
        t("announce_sent", language).format(sent=result.sent, failed=result.failed)
    )


def _parse_kv(args: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in args:
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key.strip().lower()] = value.strip()
    return fields


async def schedule_update_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Admin ``/schedule_update <date> <field=value...|cancel>`` (manual override)."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    if not await has_admin_access(update):
        await message.reply_text(t("admin_refused", language))
        return
    args: list[str] = list(getattr(context, "args", None) or [])
    if not args:
        await message.reply_text(t("sched_update_usage", language))
        return
    date = args[0]
    rest = args[1:]
    store = _store()
    if rest and rest[0].lower() == "cancel":
        store.cancel_session(date)
        await message.reply_text(
            t("sched_update_done", language).format(action="cancelled", date=date)
        )
        return
    fields = _parse_kv(rest)
    if not fields:
        await message.reply_text(t("sched_update_usage", language))
        return
    action = store.upsert_session(date, fields)
    await message.reply_text(
        t("sched_update_done", language).format(action=action, date=date)
    )
