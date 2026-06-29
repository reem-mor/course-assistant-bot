"""Homework submission conversation flow (feature 6.5).

A PTB ConversationHandler collects the submission fields, previews the exact 4.3 email,
and sends it on confirmation. The draft lives in ``context.user_data`` for the duration of
the conversation; the student's full name is remembered across submissions. Email sending
is delegated to a configured ``EmailService`` (mocked in tests).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.i18n import Language, detect_language, t
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.domain.models import DraftAttachment, SubmissionDraft
from app.services.email import EmailService, try_get_email_service
from app.services.schedule import now_in_israel
from app.services.submission import compose_email, finalize_and_send

if TYPE_CHECKING:
    from telegram import Update

_log = get_logger("bot.submission")

# Conversation states.
NAME, TOPIC, DATE, WORK, TECH, CHALLENGES, ATTACH, PREVIEW = range(8)

# Telegram bots can download files up to ~20 MB; larger ones must be shared as links.
_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024

_DRAFT_KEY: Final = "submission_draft"
_NAME_KEY: Final = "full_name"
_WARNED_KEY: Final = "no_attachment_warned"
_LANG_KEY: Final = "submission_lang"

_SUBMIT_PATTERN = (
    r"(?i)(draft submission|submit homework|write submission email|"
    r"כתוב לי טיוטה|הגש שיעורי בית|שלח מייל הגשה)"
)


def _email_service() -> EmailService | None:
    """Factory for the configured email backend (patched in tests)."""
    return try_get_email_service(get_settings())


def _draft(context: ContextTypes.DEFAULT_TYPE) -> SubmissionDraft:
    data: dict[str, Any] = context.user_data  # type: ignore[assignment]
    draft = data.get(_DRAFT_KEY)
    if not isinstance(draft, SubmissionDraft):
        draft = SubmissionDraft()
        data[_DRAFT_KEY] = draft
    return draft


def _lang(context: ContextTypes.DEFAULT_TYPE, text: str | None = None) -> Language:
    data: dict[str, Any] = context.user_data  # type: ignore[assignment]
    if text is not None:
        data[_LANG_KEY] = detect_language(text)
    cached = data.get(_LANG_KEY)
    return cached if cached in ("he", "en") else detect_language(text)


async def start_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: begin a new draft, prefilling the remembered name if present."""
    message = update.effective_message
    if message is None:
        return ConversationHandler.END
    data: dict[str, Any] = context.user_data  # type: ignore[assignment]
    language = _lang(context, message.text)
    draft = SubmissionDraft()
    remembered = data.get(_NAME_KEY)
    data[_DRAFT_KEY] = draft
    data[_WARNED_KEY] = False
    if remembered:
        draft.full_name = remembered
        await message.reply_text(t("sub_ask_topic", language))
        return TOPIC
    await message.reply_text(t("sub_ask_name", language))
    return NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if message is None or message.text is None:
        return NAME
    language = _lang(context)
    draft = _draft(context)
    draft.full_name = message.text.strip()
    context.user_data[_NAME_KEY] = draft.full_name  # type: ignore[index]
    await message.reply_text(t("sub_ask_topic", language))
    return TOPIC


async def receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if message is None or message.text is None:
        return TOPIC
    _draft(context).topic = message.text.strip()
    await message.reply_text(t("sub_ask_date", _lang(context)))
    return DATE


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if message is None or message.text is None:
        return DATE
    language = _lang(context)
    text = message.text.strip().lower()
    if text in ("today", "היום", ""):
        date_value = now_in_israel().strftime("%d/%m/%Y")
    else:
        date_value = message.text.strip()
    _draft(context).date_ddmmyyyy = date_value
    await message.reply_text(t("sub_ask_work", language))
    return WORK


async def receive_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if message is None or message.text is None:
        return WORK
    _draft(context).work = message.text.strip()
    await message.reply_text(t("sub_ask_tech", _lang(context)))
    return TECH


async def receive_tech(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if message is None or message.text is None:
        return TECH
    _draft(context).tech = message.text.strip()
    await message.reply_text(t("sub_ask_challenges", _lang(context)))
    return CHALLENGES


async def receive_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if message is None or message.text is None:
        return CHALLENGES
    text = message.text.strip()
    _draft(context).challenges = None if text == "-" else text
    await message.reply_text(t("sub_ask_attachments", _lang(context)))
    return ATTACH


async def receive_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Capture an uploaded document/photo or a GitHub link; stay in ATTACH."""
    message = update.effective_message
    if message is None:
        return ATTACH
    language = _lang(context)
    draft = _draft(context)

    document = message.document
    if document is not None:
        if (document.file_size or 0) > _MAX_ATTACHMENT_BYTES:
            await message.reply_text(t("sub_attachment_too_large", language))
            return ATTACH
        tg_file = await context.bot.get_file(document.file_id)
        content = bytes(await tg_file.download_as_bytearray())
        draft.attachments = [
            *draft.attachments,
            DraftAttachment(
                filename=document.file_name or "attachment",
                content=content,
                mime_type=document.mime_type or "application/octet-stream",
            ),
        ]
        await message.reply_text(
            t("sub_attachment_added", language).format(name=document.file_name)
        )
        return ATTACH

    if message.text and message.text.strip().lower().startswith(("http://", "https://")):
        draft.github_link = message.text.strip()
        await message.reply_text(
            t("sub_attachment_added", language).format(name=draft.github_link)
        )
    return ATTACH


def _preview_text(draft: SubmissionDraft, language: Language) -> str:
    email = compose_email(draft, get_settings())
    att_names = [a.filename for a in draft.attachments]
    if draft.github_link:
        att_names.append(f"GitHub: {draft.github_link}")
    att_display = ", ".join(att_names) if att_names else "-"
    return "\n".join(
        [
            t("sub_preview_header", language),
            "",
            f"{t('sub_label_to', language)}: {email.to}",
            f"{t('sub_label_cc', language)}: {email.cc or '-'}",
            f"{t('sub_label_subject', language)}: {email.subject}",
            "",
            email.body,
            "",
            f"{t('sub_label_attachments', language)}: {att_display}",
        ]
    )


def _preview_keyboard(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t("sub_btn_send", language), callback_data="sub:send"),
                InlineKeyboardButton(t("sub_btn_edit", language), callback_data="sub:edit"),
                InlineKeyboardButton(t("sub_btn_cancel", language), callback_data="sub:cancel"),
            ]
        ]
    )


async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Build the draft preview and present Send/Edit/Cancel buttons."""
    message = update.effective_message
    if message is None:
        return ATTACH
    language = _lang(context)
    draft = _draft(context)
    missing = draft.missing_fields()
    if missing:
        # Shouldn't normally happen; restart collection from the name.
        await message.reply_text(t("sub_edit_restart", language))
        return NAME
    draft.mark_preview()
    await message.reply_text(
        _preview_text(draft, language), reply_markup=_preview_keyboard(language)
    )
    return PREVIEW


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the Send/Edit/Cancel inline buttons."""
    query = update.callback_query
    message = update.effective_message
    if query is None or message is None:
        return PREVIEW
    await query.answer()
    language = _lang(context)
    draft = _draft(context)
    action = (query.data or "").split(":", 1)[-1]

    if action == "cancel":
        draft.cancel()
        await message.reply_text(t("sub_cancelled", language))
        return ConversationHandler.END

    if action == "edit":
        await message.reply_text(t("sub_edit_restart", language))
        await message.reply_text(t("sub_ask_name", language))
        return NAME

    # action == "send"
    data: dict[str, Any] = context.user_data  # type: ignore[assignment]
    if not draft.has_attachment_or_link and not data.get(_WARNED_KEY):
        data[_WARNED_KEY] = True
        await message.reply_text(t("sub_no_attachments_warn", language))
        return PREVIEW

    service = _email_service()
    if service is None:
        await message.reply_text(t("sub_email_not_configured", language))
        return PREVIEW

    draft.confirm()
    try:
        message_id = await finalize_and_send(draft, service, get_settings())
    except Exception as exc:  # keep the draft, offer retry
        _log.exception("submission_send_failed")
        await message.reply_text(t("sub_send_failed", language).format(error=str(exc)))
        return PREVIEW
    await message.reply_text(t("sub_sent", language).format(message_id=message_id))
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancel during the conversation."""
    message = update.effective_message
    if message is not None:
        draft = _draft(context)
        if draft.state.value != "sent":
            draft.cancel()
        await message.reply_text(t("sub_cancelled", _lang(context)))
    return ConversationHandler.END


def build_submission_conversation() -> ConversationHandler:  # type: ignore[type-arg]
    """Construct the homework submission ConversationHandler."""
    text_only = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[
            CommandHandler("submit", start_submission),
            MessageHandler(filters.Regex(_SUBMIT_PATTERN), start_submission),
        ],
        states={
            NAME: [MessageHandler(text_only, receive_name)],
            TOPIC: [MessageHandler(text_only, receive_topic)],
            DATE: [MessageHandler(text_only, receive_date)],
            WORK: [MessageHandler(text_only, receive_work)],
            TECH: [MessageHandler(text_only, receive_tech)],
            CHALLENGES: [MessageHandler(text_only, receive_challenges)],
            ATTACH: [
                CommandHandler("done", show_preview),
                MessageHandler(filters.Document.ALL | filters.PHOTO, receive_attachment),
                MessageHandler(text_only, receive_attachment),
            ],
            PREVIEW: [CallbackQueryHandler(on_button, pattern="^sub:")],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="submission",
        persistent=False,
    )
