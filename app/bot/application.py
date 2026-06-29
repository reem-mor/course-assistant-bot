"""Telegram application factory.

Builds the ``python-telegram-bot`` Application and registers Phase 0 handlers. Wiring is
isolated from handler logic so the handlers stay unit-testable without a real bot token.
"""

from __future__ import annotations

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.admin_handlers import (
    admin_command,
    help_command,
    map_command,
    refresh_schedule_command,
    reindex_command,
)
from app.bot.admin_upload import handle_admin_upload
from app.bot.announce_flow import (
    announce_callback,
    announce_command,
    schedule_update_command,
)
from app.bot.handlers import error_handler, myid_command, text_message
from app.bot.schedule_handlers import schedule_command
from app.bot.submission_flow import build_submission_conversation
from app.bot.subscription_handlers import (
    menu_callback,
    menu_command,
    start_command,
    stop_command,
)
from app.core.settings import Settings


def build_application(settings: Settings) -> Application:  # type: ignore[type-arg]
    """Construct and configure the Telegram Application from settings.

    Raises a clear error via ``require_telegram_token`` if the bot token is missing.
    """
    token = settings.require_telegram_token()
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("map", map_command))
    application.add_handler(CommandHandler("reindex", reindex_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("refresh_schedule", refresh_schedule_command))
    application.add_handler(CommandHandler("announce", announce_command))
    application.add_handler(CommandHandler("schedule_update", schedule_update_command))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu:"))
    application.add_handler(CallbackQueryHandler(announce_callback, pattern="^ann:"))
    # The submission conversation must be registered before the generic text/upload
    # handlers so its entry keywords and active-conversation states take precedence.
    application.add_handler(build_submission_conversation())
    application.add_handler(
        MessageHandler(filters.Document.ALL | filters.PHOTO, handle_admin_upload)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message)
    )
    application.add_error_handler(error_handler)
    return application
