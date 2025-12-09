"""
One-time helper to generate Gmail OAuth token for local development.

Usage:
    python -m app.gmail_auth
Requires a OAuth client secret JSON file at ./data/google_client_secret.json
created via Google Cloud console (Desktop app). Saves token to ./data/token.json.
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from .gmail_client import SCOPES, TOKEN_PATH, CREDENTIALS_PATH


def main() -> None:
    if not CREDENTIALS_PATH.exists():
        raise SystemExit(
            f"Client secret file not found at {CREDENTIALS_PATH}. "
            "Download it from Google Cloud console (OAuth client for Desktop app)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"Token saved to {TOKEN_PATH}")


if __name__ == "__main__":
    main()
