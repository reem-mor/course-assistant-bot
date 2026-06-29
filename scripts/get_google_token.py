"""One-time helper to mint a Google OAuth refresh token for the bot.

Run this locally once to obtain a long-lived refresh token for Drive (read) and Gmail
(send). It opens a browser for consent, then prints the values to paste into ``.env``.

Usage:
    uv sync --extra auth
    uv run python scripts/get_google_token.py --client-secrets /path/to/client_secret.json

Or provide the client id/secret via flags/env:
    uv run python scripts/get_google_token.py --client-id ... --client-secret ...

The OAuth app should be set to Internal / In-production so the refresh token does not
expire (the "testing app -> 7-day expiry" pitfall). Nothing is written to disk; copy the
printed values into your .env yourself.
"""

from __future__ import annotations

import argparse
import os
import sys

# Read scope: course Drive folder. Write scope: scoped create-only (admin upload).
# Send scope: Gmail submission emails.
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
]


def _build_flow(args: argparse.Namespace) -> object:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit(
            "google-auth-oauthlib is not installed. Run: uv sync --extra auth"
        )

    if args.client_secrets:
        return InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)

    client_id = args.client_id or os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = args.client_secret or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit(
            "Provide --client-secrets <file>, or --client-id/--client-secret "
            "(or set GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET)."
        )
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    return InstalledAppFlow.from_client_config(client_config, SCOPES)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint a Google OAuth refresh token.")
    parser.add_argument("--client-secrets", help="Path to a client_secret.json file.")
    parser.add_argument("--client-id", help="OAuth client id (alternative to --client-secrets).")
    parser.add_argument("--client-secret", help="OAuth client secret.")
    parser.add_argument("--port", type=int, default=0, help="Local consent server port.")
    args = parser.parse_args()

    flow = _build_flow(args)
    creds = flow.run_local_server(port=args.port, prompt="consent")  # type: ignore[attr-defined]

    if not getattr(creds, "refresh_token", None):
        sys.exit(
            "No refresh token returned. Revoke prior access and retry with prompt=consent, "
            "or ensure the OAuth client is a Desktop app."
        )

    print("\n=== Paste these into oz_veruach_bot/.env ===")
    print(f"GOOGLE_OAUTH_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_OAUTH_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print("============================================\n")


if __name__ == "__main__":
    main()
