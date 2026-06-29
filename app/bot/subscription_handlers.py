"""Subscription + onboarding handlers (feature 6.9).

``/start`` registers (or re-activates) the user as a broadcast subscriber and greets them;
``/stop`` unsubscribes (on-demand features still work); ``/menu`` surfaces the main actions
as an inline keyboard. Subscriber state is persisted via ``SubscriberRepo``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.dispatch import dispatch_intent
from app.bot.router import Intent, IntentName, Scope
from app.core.i18n import Language, detect_language, t
from app.core.logging import get_logger
from app.repo.db import get_sessionmaker
from app.repo.repositories import SubscriberRepo

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

_log = get_logger("bot.subscription")


def _subscriber_repo() -> SubscriberRepo:
    """Factory for the subscriber repo (patched in tests)."""
    return SubscriberRepo(get_sessionmaker())


async def start_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register the user as a subscriber and greet them."""
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    language = detect_language(message.text)
    try:
        await _subscriber_repo().upsert(user.id, language=language)
    except Exception:  # greeting must work even if the DB is unavailable
        _log.exception("subscriber_upsert_failed", user_id=user.id)
    await message.reply_text(f"{t('start', language)}\n\n{t('subscribed', language)}")


async def stop_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe the user from broadcasts."""
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    language = detect_language(message.text)
    try:
        await _subscriber_repo().unsubscribe(user.id)
    except Exception:
        _log.exception("subscriber_unsubscribe_failed", user_id=user.id)
    await message.reply_text(t("unsubscribed", language))


def _menu_keyboard(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("menu_schedule", language), callback_data="menu:schedule")],
            [InlineKeyboardButton(t("menu_recording", language), callback_data="menu:recording")],
            [InlineKeyboardButton(t("menu_homework", language), callback_data="menu:homework")],
            [InlineKeyboardButton(t("menu_submit", language), callback_data="menu:submit")],
        ]
    )


async def menu_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the inline action menu."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    await message.reply_text(t("menu_header", language), reply_markup=_menu_keyboard(language))


async def menu_callback(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline menu button presses by dispatching the matching intent."""
    query = update.callback_query
    message = update.effective_message
    if query is None or message is None:
        return
    await query.answer()
    language = detect_language(message.text)
    action = (query.data or "").split(":", 1)[-1]
    if action == "submit":
        await message.reply_text(t("sub_hint_use_command", language))
        return
    mapping = {
        "schedule": Intent(name=IntentName.SCHEDULE, scope=Scope.FULL),
        "recording": Intent(name=IntentName.RECORDING, scope=Scope.ALL),
        "homework": Intent(name=IntentName.HOMEWORK_LATEST),
    }
    intent = mapping.get(action)
    if intent is None:
        return
    reply = await dispatch_intent(intent, language)
    if reply is not None:
        await message.reply_text(reply)
