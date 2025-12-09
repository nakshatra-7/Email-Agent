import os
import threading
import time
from datetime import datetime, timedelta
from typing import List

from sqlmodel import Session, select

from app.database import engine
from app.gmail_client import fetch_and_store_messages
from app.models import Email
from app.services.actions import decide_actions, execute_actions
from app.services.nlu_email import analyze_email_with_llm
from app.services.attachment_text import gather_attachment_text


POLL_SECONDS = int(os.getenv("AGENT_POLL_SECONDS", "900"))
MAX_FETCH = int(os.getenv("AGENT_FETCH_LIMIT", "10"))
GMAIL_QUERY = os.getenv("AGENT_GMAIL_QUERY", "is:unread in:inbox")


def _process_email(session: Session, email: Email) -> None:
    body = email.body or email.snippet or ""
    attachment_text = gather_attachment_text(email)
    if attachment_text:
        body = f"{body}\n\nAttachment excerpts:\n{attachment_text}"
    analysis = analyze_email_with_llm(
        subject=email.subject, sender=email.from_address, body=body
    )
    actions = decide_actions(analysis)
    execute_actions(
        email_id=str(email.id),
        original_email_body=body,
        analysis=analysis,
        actions=actions,
    )
    email.intent_analysis = analysis.model_dump()
    email.intent_actions = actions
    email.processed = True
    email.processed_at = datetime.utcnow()
    email.updated_at = datetime.utcnow()
    session.add(email)
    session.commit()
    session.refresh(email)


def run_once() -> int:
    with Session(engine) as session:
        fetch_and_store_messages(
            session=session, query=GMAIL_QUERY, max_results=MAX_FETCH
        )

        statement = select(Email).where(Email.processed == False)  # noqa: E712
        to_process: List[Email] = session.exec(statement).all()

        count = 0
        for email in to_process:
            try:
                _process_email(session, email)
                count += 1
            except Exception as exc:  # pragma: no cover - operational logging
                print(f"[ERROR] Processing email id={email.id}: {exc}")
        return count


def _loop() -> None:
    while True:
        started = datetime.utcnow()
        print(f"[AGENT] Tick start @ {started.isoformat()}")
        processed = run_once()
        print(f"[AGENT] Tick done. processed={processed}")
        elapsed = datetime.utcnow() - started
        sleep_for = max(POLL_SECONDS - elapsed.total_seconds(), 0)
        time.sleep(sleep_for)


def start_background_loop() -> None:
    """Launch the agent loop in a background thread."""
    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    print("[AGENT] Background loop started.")


if __name__ == "__main__":
    print(
        f"[AGENT] Starting loop. poll={POLL_SECONDS}s query='{GMAIL_QUERY}' max_fetch={MAX_FETCH}"
    )
    _loop()
