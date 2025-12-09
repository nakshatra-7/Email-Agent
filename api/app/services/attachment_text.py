from pathlib import Path
from typing import List

from pypdf import PdfReader

from app.gmail_client import download_attachment
from app.models import Email


def extract_pdf_text(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception as exc:  # pragma: no cover - best-effort extraction
        print(f"[ATTACHMENT] Failed to read PDF {path}: {exc}")
        return ""


def gather_attachment_text(email: Email) -> str:
    """
    Download PDF attachments for a Gmail-synced email and return concatenated text.
    """
    if not email.gmail_id or not email.attachments:
        return ""

    chunks: List[str] = []
    for att in email.attachments:
        if att.get("mimeType") != "application/pdf":
            continue
        attachment_id = att.get("attachment_id")
        if not attachment_id:
            continue
        filename = att.get("filename", "(unknown)")
        try:
            path = download_attachment(
                gmail_id=email.gmail_id,
                attachment_id=attachment_id,
                filename=filename,
            )
            text = extract_pdf_text(Path(path))
            if text:
                chunks.append(f"Attachment: {filename}\n{text}")
        except Exception as exc:  # pragma: no cover - best effort
            print(f"[ATTACHMENT] Skipping {filename}: {exc}")
    return "\n\n".join(chunks)
