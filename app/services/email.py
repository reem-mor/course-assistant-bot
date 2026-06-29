"""Email service: one interface, two backends.

Gmail API (``gmail.send``) is preferred when Google OAuth is configured; SMTP + App
Password is the fallback. Recipient addresses come only from config
(``HW_TO_EMAIL`` / ``HW_CC_EMAIL``), never hardcoded. Blocking SDK/smtplib calls run in a
thread so the event loop is never blocked. All sending is mocked in tests.
"""

from __future__ import annotations

import asyncio
import base64
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Protocol, runtime_checkable

from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.core.settings import Settings

_log = get_logger("email")

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


@dataclass(frozen=True, slots=True)
class EmailAttachment:
    """An attachment to include in an outgoing email."""

    filename: str
    content: bytes
    mime_type: str


@runtime_checkable
class EmailService(Protocol):
    """Sends homework submission emails."""

    async def send(
        self,
        *,
        to: str,
        cc: str | None,
        subject: str,
        body: str,
        attachments: list[EmailAttachment],
    ) -> str:
        """Send an email and return the provider message id."""
        ...


def _build_mime(
    *,
    sender: str | None,
    to: str,
    cc: str | None,
    subject: str,
    body: str,
    attachments: list[EmailAttachment],
) -> EmailMessage:
    """Build a MIME message with optional attachments."""
    message = EmailMessage()
    if sender:
        message["From"] = sender
    message["To"] = to
    if cc:
        message["Cc"] = cc
    message["Subject"] = subject
    message.set_content(body)
    for att in attachments:
        maintype, _, subtype = att.mime_type.partition("/")
        message.add_attachment(
            att.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=att.filename,
        )
    return message


class GmailEmailService:
    """EmailService backed by the Gmail API (gmail.send).

    The Drive/Gmail client is built lazily on first send so constructing this service
    (e.g. for backend selection) never performs network/discovery work.
    """

    def __init__(
        self,
        client: Any = None,
        *,
        settings: Settings | None = None,
        sender: str | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._sender = sender

    def _ensure_client(self) -> Any:
        if self._client is None:
            if self._settings is None:
                raise ExternalServiceError("Gmail client not configured", service="gmail")
            self._client = _build_gmail_client(self._settings)
        return self._client

    async def send(
        self,
        *,
        to: str,
        cc: str | None,
        subject: str,
        body: str,
        attachments: list[EmailAttachment],
    ) -> str:
        client = self._ensure_client()
        message = _build_mime(
            sender=self._sender, to=to, cc=cc, subject=subject, body=body,
            attachments=attachments,
        )
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

        def _send() -> Any:
            return (
                client.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )

        try:
            result = await asyncio.to_thread(_send)
        except Exception as exc:  # surface a typed error to the caller
            raise ExternalServiceError(str(exc), service="gmail") from exc
        return str(result.get("id", ""))


class SmtpEmailService:
    """EmailService backed by SMTP + App Password (fallback)."""

    def __init__(
        self, *, host: str, port: int, user: str, password: str
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    async def send(
        self,
        *,
        to: str,
        cc: str | None,
        subject: str,
        body: str,
        attachments: list[EmailAttachment],
    ) -> str:
        message = _build_mime(
            sender=self._user, to=to, cc=cc, subject=subject, body=body,
            attachments=attachments,
        )

        def _send() -> str:
            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.send_message(message)
            return str(message.get("Message-ID", ""))

        try:
            return await asyncio.to_thread(_send)
        except Exception as exc:
            raise ExternalServiceError(str(exc), service="smtp") from exc


def _build_gmail_client(settings: Settings) -> Any:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(  # type: ignore[no-untyped-call]
        token=None,
        refresh_token=settings.google_oauth_refresh_token.get_secret_value()
        if settings.google_oauth_refresh_token
        else None,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret.get_secret_value()
        if settings.google_oauth_client_secret
        else None,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[GMAIL_SEND_SCOPE],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def build_email_service(settings: Settings) -> EmailService | None:
    """Pick an email backend from config: Gmail (preferred) or SMTP, else None."""
    if settings.google_oauth_refresh_token and settings.google_oauth_client_id:
        return GmailEmailService(settings=settings)
    if settings.smtp_host and settings.smtp_user and settings.smtp_pass:
        return SmtpEmailService(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_pass.get_secret_value(),
        )
    _log.info("email_not_configured")
    return None


def try_get_email_service(settings: Settings) -> EmailService | None:
    """Return a configured EmailService, or None if neither backend is configured."""
    return build_email_service(settings)
