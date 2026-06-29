"""Google Drive access (read-only) with pluggable auth.

``DriveService`` is read-only over the course folder; ``DriveUploader`` (Phase 5) is the
single, scoped, create-only write path. The synchronous ``google-api-python-client`` is
wrapped in ``asyncio.to_thread`` with a small retry/backoff helper so the event loop is
never blocked. Auth is pluggable: OAuth refresh-token credentials (v1 default) or a
service account.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from app.core.errors import ConfigurationError, ExternalServiceError
from app.core.logging import get_logger
from app.core.settings import Settings, get_settings

_log = get_logger("drive")

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
# Scoped write access for the admin-upload feature only (create files the bot owns).
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
_LIST_FIELDS = "files(id,name,mimeType,size,modifiedTime,createdTime),nextPageToken"


@runtime_checkable
class DriveService(Protocol):
    """Read-only access to the course Google Drive folder."""

    async def list_children(self, folder_id: str) -> list[dict[str, Any]]: ...

    async def read_file_content(self, file_id: str) -> str: ...

    async def download_file(self, file_id: str) -> bytes: ...


@runtime_checkable
class DriveUploader(Protocol):
    """Scoped, create-only write access for the admin upload feature (Phase 5)."""

    async def upload_file(
        self,
        *,
        parent_folder_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
    ) -> str: ...


def build_drive_client(settings: Settings) -> Any:
    """Build a Drive v3 client using whichever auth mode is configured.

    Prefers OAuth (Re'em's account, v1 default); falls back to a service account.
    Raises ConfigurationError if neither is configured.
    """
    # Imported lazily so the bot can start (and tests can run) without Google libs wired.
    from googleapiclient.discovery import build

    if settings.google_oauth_refresh_token and settings.google_oauth_client_id:
        from google.oauth2.credentials import Credentials

        creds = Credentials(  # type: ignore[no-untyped-call]
            token=None,
            refresh_token=settings.google_oauth_refresh_token.get_secret_value(),
            client_id=settings.google_oauth_client_id,
            client_secret=(
                settings.google_oauth_client_secret.get_secret_value()
                if settings.google_oauth_client_secret
                else None
            ),
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[DRIVE_READONLY_SCOPE],
        )
    elif settings.google_sa_json:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            settings.google_sa_json, scopes=[DRIVE_READONLY_SCOPE]
        )
    else:
        raise ConfigurationError(
            "Google Drive is not configured. Set GOOGLE_OAUTH_* or GOOGLE_SA_JSON."
        )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


class GoogleDriveService:
    """``DriveService`` backed by the Drive v3 API (read-only)."""

    def __init__(self, client: Any, *, max_attempts: int = 3) -> None:
        self._client = client
        self._max_attempts = max_attempts

    async def _execute(self, request: Any) -> Any:
        """Run a blocking Drive request in a thread, retrying transient failures."""
        from googleapiclient.errors import HttpError

        delay = 0.5
        last_exc: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return await asyncio.to_thread(request.execute)
            except HttpError as exc:
                status = getattr(exc, "status_code", None) or getattr(
                    getattr(exc, "resp", None), "status", None
                )
                if status not in (429, 500, 502, 503, 504) or attempt == self._max_attempts:
                    raise ExternalServiceError(str(exc), service="drive") from exc
                last_exc = exc
                _log.warning("drive_retry", attempt=attempt, status=status)
                await asyncio.sleep(delay)
                delay *= 2
        raise ExternalServiceError(str(last_exc), service="drive")

    async def list_children(self, folder_id: str) -> list[dict[str, Any]]:
        """List immediate, non-trashed children of a Drive folder (paginated)."""
        results: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            request = self._client.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields=_LIST_FIELDS,
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token,
            )
            response = await self._execute(request)
            results.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return results

    async def read_file_content(self, file_id: str) -> str:
        """Export a Google-native doc as plain text (used by summaries in Phase 3)."""
        request = self._client.files().export(fileId=file_id, mimeType="text/plain")
        data = await self._execute(request)
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)

    async def download_file(self, file_id: str) -> bytes:
        """Download raw file bytes (binary materials/recordings). Read-only."""
        request = self._client.files().get_media(
            fileId=file_id, supportsAllDrives=True
        )
        data = await self._execute(request)
        return data if isinstance(data, bytes) else bytes(data)


class GoogleDriveUploader:
    """The single Drive write path (admin upload). Create-only; never deletes/overwrites."""

    def __init__(self, client: Any = None, *, settings: Settings | None = None) -> None:
        self._client = client
        self._settings = settings

    def _ensure_client(self) -> Any:
        if self._client is None:
            if self._settings is None:
                raise ConfigurationError("Drive uploader not configured")
            self._client = _build_write_client(self._settings)
        return self._client

    async def upload_file(
        self,
        *,
        parent_folder_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
    ) -> str:
        """Create a new file under ``parent_folder_id`` and return its Drive id."""
        from googleapiclient.http import MediaInMemoryUpload

        client = self._ensure_client()

        def _create() -> Any:
            media = MediaInMemoryUpload(content, mimetype=mime_type, resumable=False)
            return (
                client.files()
                .create(
                    body={"name": filename, "parents": [parent_folder_id]},
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )

        try:
            result = await asyncio.to_thread(_create)
        except Exception as exc:
            raise ExternalServiceError(str(exc), service="drive_upload") from exc
        return str(result.get("id", ""))


def _build_write_client(settings: Settings) -> Any:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not (settings.google_oauth_refresh_token and settings.google_oauth_client_id):
        raise ConfigurationError("Drive write requires Google OAuth credentials.")
    creds = Credentials(  # type: ignore[no-untyped-call]
        token=None,
        refresh_token=settings.google_oauth_refresh_token.get_secret_value(),
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret.get_secret_value()
        if settings.google_oauth_client_secret
        else None,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[DRIVE_FILE_SCOPE],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def build_drive_uploader(settings: Settings) -> GoogleDriveUploader | None:
    """Return a create-only uploader if Drive write is enabled and configured, else None."""
    if not settings.drive_write_enabled:
        return None
    if not (settings.google_oauth_refresh_token and settings.google_oauth_client_id):
        _log.info("drive_write_unconfigured")
        return None
    return GoogleDriveUploader(settings=settings)


@lru_cache(maxsize=1)
def get_drive_service() -> GoogleDriveService:
    """Return a cached Drive service, building the client from settings.

    Raises ConfigurationError if Drive auth is not configured; callers that want a soft
    failure should use ``try_get_drive_service``.
    """
    return GoogleDriveService(build_drive_client(get_settings()))


def try_get_drive_service() -> GoogleDriveService | None:
    """Return the Drive service, or None if Drive is not configured."""
    try:
        return get_drive_service()
    except ConfigurationError:
        return None
