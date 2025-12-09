from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models import Email
from ..services.agent_runner import run_once
from ..services.attachment_text import gather_attachment_text

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/sync_once", summary="Run one agent tick (fetch/analyze/act)")
def sync_once() -> dict:
    processed = run_once()
    return {"processed": processed}


@router.get("/events", summary="List recent processed emails/actions")
def list_events(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> List[dict]:
    statement = (
        select(Email)
        .where(Email.processed == True)  # noqa: E712
        .order_by(Email.processed_at.desc().nullslast(), Email.updated_at.desc())
        .limit(limit)
    )
    emails = session.exec(statement).all()
    events = []
    for email in emails:
        analysis = email.intent_analysis or {}
        attachment_excerpt = ""
        try:
            attachment_excerpt = gather_attachment_text(email)
            if attachment_excerpt:
                attachment_excerpt = attachment_excerpt[:700]
        except Exception:
            attachment_excerpt = ""
        events.append(
            {
                "id": email.id,
                "subject": email.subject,
                "from": email.from_address,
                "to": email.to_address,
                "intent_actions": email.intent_actions,
                "intent_analysis": analysis,
                "processed_at": email.processed_at,
                "updated_at": email.updated_at,
                "urgency": analysis.get("urgency"),
                "summary": analysis.get("suggested_summary"),
                "needs_reply": analysis.get("needs_reply"),
                "reply_complexity": analysis.get("reply_complexity"),
                "contains_meeting": analysis.get("contains_meeting"),
                "meeting_details": analysis.get("meeting_details"),
                "has_attachments": bool(email.attachments),
                "attachments_count": len(email.attachments or []),
                "attachment_excerpt": attachment_excerpt,
            }
        )
    return events
