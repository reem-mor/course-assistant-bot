"""Admin upload -> broadcast (feature 6.8).

An admin sends a document/photo to the bot (optionally captioned like ``lesson 12
homework``). The bot acknowledges, broadcasts to all subscribers, and - only when Drive
write is enabled and configured - files the document into the course Presentations tree via
the create-only ``GoogleDriveUploader``. Non-admins are politely refused.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.bot.admin_handlers import is_admin
from app.core.i18n import DEFAULT_LANGUAGE, detect_language, t
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.repo.db import get_sessionmaker
from app.repo.repositories import BroadcastLogRepo, SubscriberRepo
from app.services.drive import build_drive_uploader, try_get_drive_service
from app.services.drive_parser import file_id, file_name, is_folder, lesson_number_from_title
from app.services.lesson_map_store import YamlLessonMapStore
from app.services.notifier import Notifier, TelegramNotifier

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

_log = get_logger("bot.admin_upload")

_LESSON_RE = re.compile(r"(?:lesson|שיעור)\s*#?\s*(\d+)", re.IGNORECASE)
_KIND_WORDS: dict[str, str] = {
    "homework": "homework", "hw": "homework", "מטלה": "homework",
    "slides": "slides", "מצגת": "slides",
    "code": "code", "recording": "recording", "הקלטה": "recording",
}


@dataclass(frozen=True)
class UploadIntent:
    """Parsed admin-upload caption."""

    lesson: int | None
    kind: str


def parse_caption(caption: str | None) -> UploadIntent:
    """Parse an optional caption like 'lesson 12 homework' into lesson + kind."""
    if not caption:
        return UploadIntent(lesson=None, kind="other")
    lowered = caption.lower()
    lesson_match = _LESSON_RE.search(caption)
    lesson = int(lesson_match.group(1)) if lesson_match else None
    kind = "other"
    for word, mapped in _KIND_WORDS.items():
        if word in lowered:
            kind = mapped
            break
    return UploadIntent(lesson=lesson, kind=kind)


def _notifier(bot: object) -> Notifier:
    sm = get_sessionmaker()
    return TelegramNotifier(
        bot, SubscriberRepo(sm), BroadcastLogRepo(sm),
        rate_per_sec=get_settings().broadcast_rate_per_sec,
    )


async def _resolve_presentation_folder(lesson: int | None) -> str | None:
    """Find the presentation 'Lesson N' subfolder id, else the presentations root."""
    lesson_map = YamlLessonMapStore().load()
    root = lesson_map.roots.presentations_folder
    drive = try_get_drive_service()
    if drive is None or lesson is None:
        return root
    for child in await drive.list_children(root):
        if is_folder(child) and lesson_number_from_title(file_name(child)) == lesson:
            return file_id(child)
    return root


async def handle_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acknowledge an admin upload, broadcast it, and optionally file it to Drive."""
    message = update.effective_message
    if message is None or message.document is None:
        return
    language = detect_language(message.caption)
    if not is_admin(update):
        from app.core.i18n import t as _t

        await message.reply_text(_t("admin_refused", language))
        return

    document = message.document
    parsed = parse_caption(message.caption)
    await message.reply_text(t("upload_ack", language))

    settings = get_settings()
    filed_id: str | None = None
    uploader = build_drive_uploader(settings)
    if uploader is not None:
        parent = await _resolve_presentation_folder(parsed.lesson)
        if parent is not None:
            tg_file = await context.bot.get_file(document.file_id)
            content = bytes(await tg_file.download_as_bytearray())
            filed_id = await uploader.upload_file(
                parent_folder_id=parent,
                filename=document.file_name or "upload",
                content=content,
                mime_type=document.mime_type or "application/octet-stream",
            )

    kind_label = t(f"kind_{parsed.kind}", DEFAULT_LANGUAGE)
    lesson_suffix = (
        t("notify_lesson_suffix", DEFAULT_LANGUAGE).format(lesson=f"Lesson {parsed.lesson}")
        if parsed.lesson
        else ""
    )
    broadcast_message = t("notify_new_material", DEFAULT_LANGUAGE).format(
        kind=kind_label, lesson=lesson_suffix, name=document.file_name or "file",
        link="(via the bot)",
    )
    result = await _notifier(context.bot).broadcast(
        idempotency_key=f"admin-upload:{uuid.uuid4()}", message=broadcast_message
    )

    await message.reply_text(
        t("upload_broadcasted", language).format(sent=result.sent, failed=result.failed)
    )
    if filed_id:
        await message.reply_text(t("upload_drive_filed", language).format(file_id=filed_id))
    elif not settings.drive_write_enabled:
        await message.reply_text(t("upload_drive_disabled", language))
