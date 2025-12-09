import base64
import json
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlmodel import Session, select

from .models import Email, EmailStatus

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_PATH = Path("./data/token.json")
CREDENTIALS_PATH = Path(
    os.getenv("GOOGLE_CLIENT_SECRET_PATH", "./data/google_client_secret.json")
)


def _load_credentials() -> Credentials:
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    else:
        raise RuntimeError(
            f"Token file not found at {TOKEN_PATH}. Run `python -m app.gmail_auth` first."
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def build_service():
    creds = _load_credentials()
    return build("gmail", "v1", credentials=creds)


def _parse_headers(headers: List[Dict[str, str]]) -> Dict[str, str]:
    lookup = {}
    for header in headers:
        name = header.get("name")
        value = header.get("value")
        if name and value:
            lookup[name.lower()] = value
    return lookup


def _parse_attachments(parts: List[Dict]) -> List[dict]:
    attachments: List[dict] = []
    for part in parts:
        filename = part.get("filename")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        mime_type = part.get("mimeType")
        size = body.get("size")
        if attachment_id and filename:
            attachments.append(
                {
                    "filename": filename,
                    "mimeType": mime_type,
                    "size": size,
                    "attachment_id": attachment_id,
                }
            )
        if part.get("parts"):
            attachments.extend(_parse_attachments(part["parts"]))
    return attachments


def fetch_and_store_messages(
    session: Session, query: str = "in:inbox", max_results: int = 10
) -> List[Email]:
    """Fetch messages from Gmail and persist to DB if not present."""
    service = build_service()
    emails: List[Email] = []
    try:
        result = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = result.get("messages", [])
        for msg_meta in messages:
            msg_id = msg_meta["id"]
            # Skip if already synced
            existing = session.exec(
                select(Email).where(Email.gmail_id == msg_id)
            ).first()
            if existing:
                emails.append(existing)
                continue

            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            payload = msg.get("payload", {})
            headers = _parse_headers(payload.get("headers", []))
            attachments = _parse_attachments(payload.get("parts", []))
            body_data = ""
            if payload.get("body", {}).get("data"):
                body_data = base64.urlsafe_b64decode(
                    payload["body"]["data"]
                ).decode("utf-8", errors="ignore")

            email = Email(
                subject=headers.get("subject", "(no subject)"),
                body=body_data,
                from_address=headers.get("from", ""),
                to_address=headers.get("to", ""),
                status=EmailStatus.sent,
                tags=[],
                attachments=attachments,
                gmail_id=msg_id,
                thread_id=msg.get("threadId"),
                snippet=msg.get("snippet"),
            )
            session.add(email)
            session.commit()
            session.refresh(email)
            emails.append(email)
    except HttpError as exc:
        raise RuntimeError(f"Gmail API error: {exc}") from exc
    return emails


def _safe_attachment_path(
    output_dir: Path, gmail_id: str, attachment_id: str, filename: Optional[str] = None
) -> Path:
    base = (Path(filename).name if filename else "").replace(os.sep, "_")
    if not base:
        base = "attachment"
    stem = Path(base).stem
    ext = Path(base).suffix
    digest = hashlib.sha1(f"{gmail_id}_{attachment_id}".encode()).hexdigest()[:8]
    # Keep stem short to avoid OS limits; append a short hash.
    stem = stem[:60]
    safe_name = f"{stem}_{digest}{ext}" if stem else f"file_{digest}{ext}"
    return output_dir / safe_name


def download_attachment(
    gmail_id: str,
    attachment_id: str,
    output_dir: Path = Path("./data/attachments"),
    filename: Optional[str] = None,
) -> Path:
    """Download a single attachment to disk and return its path."""
    service = build_service()
    try:
        attachment = (
            service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=gmail_id, id=attachment_id)
            .execute()
        )
        data = base64.urlsafe_b64decode(attachment["data"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = _safe_attachment_path(
            output_dir=output_dir,
            gmail_id=gmail_id,
            attachment_id=attachment_id,
            filename=filename,
        )
        output_path.write_bytes(data)
        return output_path
    except HttpError as exc:
        raise RuntimeError(f"Failed to download attachment: {exc}") from exc


def send_email_via_gmail(email: Email) -> Dict:
    """Send an Email record via Gmail."""
    service = build_service()
    message = EmailMessage()
    message["To"] = email.to_address
    message["From"] = email.from_address
    message["Subject"] = email.subject
    message.set_content(email.body)
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        send_result = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )
        return send_result
    except HttpError as exc:
        raise RuntimeError(f"Failed to send email: {exc}") from exc
