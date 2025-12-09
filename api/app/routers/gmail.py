from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from ..database import get_session
from ..gmail_client import (
    download_attachment,
    fetch_and_store_messages,
    send_email_via_gmail,
)
from ..models import Email, EmailStatus
from ..services.actions import decide_actions
from ..services.nlu_email import analyze_email_with_llm
from ..services.attachment_text import gather_attachment_text
from datetime import datetime

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.post(
    "/sync",
    response_model=List[Email],
    summary="Sync latest Gmail messages into the local DB",
)
def sync_gmail(
    query: str = Query("in:inbox", description="Gmail search query"),
    max_results: int = Query(10, ge=1, le=50, description="Number of emails to fetch"),
    session: Session = Depends(get_session),
) -> List[Email]:
    emails = fetch_and_store_messages(session=session, query=query, max_results=max_results)
    return emails


@router.get(
    "/messages",
    response_model=List[Email],
    summary="List synced Gmail messages",
)
def list_synced_emails(
    status: Optional[EmailStatus] = None, session: Session = Depends(get_session)
) -> List[Email]:
    statement = select(Email).where(Email.gmail_id.is_not(None))
    if status:
        statement = statement.where(Email.status == status)
    statement = statement.order_by(Email.created_at.desc())
    return session.exec(statement).all()


@router.post(
    "/send/{email_id}",
    response_model=dict,
    summary="Send a stored email via Gmail",
)
def send_email(email_id: int, session: Session = Depends(get_session)) -> dict:
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
        )
    result = send_email_via_gmail(email)
    email.status = EmailStatus.sent
    session.add(email)
    session.commit()
    session.refresh(email)
    return result


@router.get(
    "/attachments/{gmail_id}/{attachment_id}",
    summary="Download a Gmail attachment to disk",
)
def get_attachment(
    gmail_id: str,
    attachment_id: str,
) -> dict:
    path = download_attachment(gmail_id=gmail_id, attachment_id=attachment_id)
    return {"saved_to": str(path)}


@router.post(
    "/analyze/{email_id}",
    response_model=Email,
    summary="Run LLM analysis + derive actions for a stored Gmail message",
)
def analyze_email(
    email_id: int,
    session: Session = Depends(get_session),
) -> Email:
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
        )

    # Use full body when present, otherwise fall back to snippet. Add PDF text if available.
    body_text = email.body or email.snippet or ""
    attachment_text = gather_attachment_text(email)
    if attachment_text:
        body_text = f"{body_text}\n\nAttachment excerpts:\n{attachment_text}"
    analysis = analyze_email_with_llm(
        subject=email.subject, sender=email.from_address, body=body_text
    )
    actions = decide_actions(analysis)

    email.intent_analysis = analysis.model_dump()
    email.intent_actions = actions
    email.updated_at = datetime.utcnow()

    session.add(email)
    session.commit()
    session.refresh(email)
    return email
