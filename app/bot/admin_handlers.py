"""Admin handlers: the owner-gated ``/map`` command (view / suggest / link).

`/map` is owner-only (brief 6.11). It shows the lesson_map, surfaces auto-suggested links
(never auto-applied), and lets the owner confirm a link, persisted to the YAML store.
A reusable role gate politely refuses non-owners/non-admins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.i18n import Language, detect_language, t
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.lesson_map_store import YamlLessonMapStore
from app.services.schedule import get_schedule_service
from app.services.suggester import suggest_recording_links

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

    from app.repo.repositories import AdminRepo

_log = get_logger("bot.admin")


def _store() -> YamlLessonMapStore:
    """Factory for the lesson_map store (patched in tests)."""
    return YamlLessonMapStore()


def is_owner(update: Update) -> bool:
    """True if the update's user is on the owner allowlist."""
    user = update.effective_user
    return user is not None and get_settings().is_owner(user.id)


def is_admin(update: Update) -> bool:
    """True if the update's user is an env-listed admin (owners are implicitly admins)."""
    user = update.effective_user
    return user is not None and get_settings().is_admin(user.id)


def _admin_repo() -> AdminRepo:
    from app.repo.db import get_sessionmaker
    from app.repo.repositories import AdminRepo

    return AdminRepo(get_sessionmaker())


async def has_admin_access(update: Update) -> bool:
    """True if the user is an env admin/owner OR a DB-managed admin."""
    user = update.effective_user
    if user is None:
        return False
    if get_settings().is_admin(user.id):
        return True
    try:
        return await _admin_repo().contains(user.id)
    except Exception:  # DB unavailable -> fall back to env allowlist only
        _log.exception("admin_db_check_failed", user_id=user.id)
        return False


def _format_map(language: Language) -> str:
    lesson_map = _store().load()
    lines = [t("map_header", language), "", t("map_recordings_label", language)]
    for label, folder_id in sorted(lesson_map.recordings_by_alex_label.items()):
        lines.append(f"  Lesson {label}: {folder_id}")
    lines.append("")
    lines.append(t("map_links_label", language))
    if not lesson_map.session_links:
        lines.append(f"  {t('map_no_links', language)}")
    else:
        for date, link in sorted(lesson_map.session_links.items()):
            lines.append(
                f"  {date}: rec={link.recording_alex_label} pres={link.presentation_alex_label}"
            )
    return "\n".join(lines)


def _format_suggestions(language: Language) -> str:
    suggestions = suggest_recording_links(get_schedule_service(), _store().load())
    if not suggestions:
        return t("map_suggest_none", language)
    lines = [t("map_suggest_header", language)]
    for s in suggestions:
        lines.append(
            f"  {s.session_date} → rec={s.recording_alex_label}  ({s.session_title})"
        )
    return "\n".join(lines)


def _parse_label(token: str, prefix: str) -> int | None:
    """Parse a ``prefix=<int>`` token, returning the int or None."""
    if token.startswith(f"{prefix}="):
        value = token.split("=", 1)[1]
        return int(value) if value.isdigit() else None
    return None


def _handle_link(args: list[str], language: Language) -> str:
    """Apply a `/map link <date> rec=<n> pres=<n>` command, persisting the link."""
    if not args:
        return t("map_usage", language)
    session_date = args[0]
    rec: int | None = None
    pres: int | None = None
    for token in args[1:]:
        rec = _parse_label(token, "rec") if rec is None else rec
        pres = _parse_label(token, "pres") if pres is None else pres
    _store().set_link(
        session_date, recording_alex_label=rec, presentation_alex_label=pres
    )
    return t("map_link_saved", language).format(date=session_date, rec=rec, pres=pres)


async def reindex_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only ``/reindex``: rebuild the RAG materials index."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    if not is_owner(update):
        await message.reply_text(t("owner_refused", language))
        return
    from app.services.drive import try_get_drive_service
    from app.services.embeddings import get_embedder
    from app.services.indexer import MaterialsIndexer
    from app.services.vectorstore_db import get_vector_store

    drive = try_get_drive_service()
    embedder = get_embedder()
    if drive is None or embedder is None:
        await message.reply_text(t("reindex_unavailable", language))
        return
    await message.reply_text(t("reindex_started", language))
    indexer = MaterialsIndexer(drive, _store().load(), embedder, get_vector_store())
    count = await indexer.reindex()
    await message.reply_text(t("reindex_done", language).format(count=count))


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only ``/map``: view, suggest, or link lesson_map entries."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    if not is_owner(update):
        _log.warning("map_denied", user_id=getattr(update.effective_user, "id", None))
        await message.reply_text(t("owner_refused", language))
        return
    args: list[str] = list(getattr(context, "args", None) or [])
    if not args:
        await message.reply_text(_format_map(language))
        return
    sub = args[0].lower()
    if sub == "suggest":
        await message.reply_text(_format_suggestions(language))
    elif sub == "link":
        await message.reply_text(_handle_link(args[1:], language))
    else:
        await message.reply_text(t("map_usage", language))


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only ``/admin add|remove|list`` for DB-managed admins."""
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    language = detect_language(message.text)
    if not is_owner(update):
        await message.reply_text(t("owner_refused", language))
        return
    args: list[str] = list(getattr(context, "args", None) or [])
    repo = _admin_repo()
    if len(args) >= 2 and args[0].lower() == "add" and args[1].isdigit():
        await repo.add(int(args[1]), added_by=user.id)
        await message.reply_text(t("admin_added", language).format(id=args[1]))
    elif len(args) >= 2 and args[0].lower() == "remove" and args[1].isdigit():
        await repo.remove(int(args[1]))
        await message.reply_text(t("admin_removed", language).format(id=args[1]))
    elif args and args[0].lower() == "list":
        ids = await repo.list_ids()
        await message.reply_text(
            t("admin_list", language).format(ids=", ".join(map(str, ids)) or "-")
        )
    else:
        await message.reply_text(t("admin_usage", language))


async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Role-aware ``/help`` listing available commands."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    parts = [t("help_header", language), "", t("help_everyone", language)]
    if await has_admin_access(update):
        parts += ["", t("help_admin", language)]
    if is_owner(update):
        parts += ["", t("help_owner", language)]
    await message.reply_text("\n".join(parts))


async def refresh_schedule_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Owner-only ``/refresh_schedule``: force a website re-scrape and report the diff."""
    message = update.effective_message
    if message is None:
        return
    language = detect_language(message.text)
    if not is_owner(update):
        await message.reply_text(t("owner_refused", language))
        return
    from app.services.schedule import get_schedule_service
    from app.workers.schedule_refresh import ScheduleRefresher, format_diff

    await message.reply_text(t("refresh_running", language))
    refresher = ScheduleRefresher(get_schedule_service(), context.bot, get_settings())
    diff = await refresher.run_once()
    await message.reply_text(format_diff(diff))
