from typing import List, Literal

try:
    # Prefer the concrete model if available in the codebase.
    from app.services.nlu_email import EmailAnalysis
except ImportError:  # pragma: no cover - fallback if path differs
    from pydantic import BaseModel

    class EmailAnalysis(BaseModel):  # type: ignore
        pass


Action = Literal[
    "NOTIFY_USER",
    "CREATE_CALENDAR_EVENT",
    "AUTO_DRAFT_REPLY",
    "SUGGEST_REPLY_DRAFT",
    "SUMMARY_ONLY",
    "NO_ACTION",
]


def _add_action(actions: List[Action], action: Action) -> None:
    if action not in actions:
        actions.append(action)


def decide_actions(analysis: EmailAnalysis) -> List[Action]:
    """
    Policy layer translating EmailAnalysis into actionable steps for the agent.
    """
    actions: List[Action] = []

    urgency = getattr(analysis, "urgency", None)
    needs_reply = getattr(analysis, "needs_reply", False)
    action_required = getattr(analysis, "action_required", False)
    reply_complexity = getattr(analysis, "reply_complexity", "none")
    email_category = getattr(analysis, "email_category", None)
    sender_role = getattr(analysis, "sender_role", None)
    notification_recommended = getattr(analysis, "notification_recommended", False)

    # Recruiter mails: always notify.
    if sender_role == "recruiter":
        _add_action(actions, "NOTIFY_USER")

    # Professor / academic mails: prefer notify and suggest draft if reply needed.
    if sender_role == "professor" or email_category == "academic":
        _add_action(actions, "NOTIFY_USER")
        if needs_reply and urgency in ("high", "critical"):
            _add_action(actions, "SUGGEST_REPLY_DRAFT")

    # Notifications: medium and above when recommended.
    if urgency in ("critical", "high", "medium") and notification_recommended:
        _add_action(actions, "NOTIFY_USER")

    # Calendar creation when meeting info is present.
    meeting = getattr(analysis, "meeting_details", None)
    has_meeting_time = bool(
        meeting
        and getattr(meeting, "date", None)
        and getattr(meeting, "start_time", None)
    )
    if getattr(analysis, "contains_meeting", False) and has_meeting_time:
        _add_action(actions, "CREATE_CALENDAR_EVENT")

    # Replies: only auto-draft for high/critical + simple; suggest for high/critical + complex.
    if action_required and needs_reply:
        if urgency in ("high", "critical") and reply_complexity == "simple":
            _add_action(actions, "AUTO_DRAFT_REPLY")
        elif urgency in ("high", "critical") and reply_complexity == "complex":
            _add_action(actions, "SUGGEST_REPLY_DRAFT")

    # Medium urgency: notify and summarize if no draft was added.
    if urgency == "medium":
        _add_action(actions, "SUMMARY_ONLY")

    # Low-value mail -> summary only, avoid notify.
    if urgency == "low" and email_category in ("marketing", "spam"):
        _add_action(actions, "SUMMARY_ONLY")
        # Avoid over-notifying low-value mail; do not add NOTIFY_USER here.

    # Low urgency, not marketing/spam: still summarize, no notify.
    if urgency == "low" and email_category not in ("marketing", "spam"):
        _add_action(actions, "SUMMARY_ONLY")

    if not actions:
        actions = ["NO_ACTION"]

    return actions


# --- Action executors (stubbed for now) ---
def notify_user(email_id: str, analysis: EmailAnalysis) -> None:
    summary = getattr(analysis, "suggested_summary", "") or "[no summary]"
    urgency = getattr(analysis, "urgency", "unknown")
    print(f"[NOTIFY] email={email_id} urgency={urgency} summary={summary}")


def create_calendar_event(email_id: str, analysis: EmailAnalysis) -> None:
    md = getattr(analysis, "meeting_details", None)
    if md:
        print(
            "[CALENDAR] email={email_id} title={title} date={date} "
            "start={start} end={end} tz={tz} location={loc} link={link}".format(
                email_id=email_id,
                title=getattr(md, "title", None) or "Meeting",
                date=getattr(md, "date", None) or "TBD",
                start=getattr(md, "start_time", None) or "TBD",
                end=getattr(md, "end_time", None) or "TBD",
                tz=getattr(md, "timezone", None) or "TBD",
                loc=getattr(md, "location", None) or "TBD",
                link=getattr(md, "online_meeting_link", None) or "-",
            )
        )
    else:
        print(f"[CALENDAR] email={email_id} meeting details missing")


def auto_draft_reply(email_id: str, original_email_body: str, analysis: EmailAnalysis) -> None:
    summary = getattr(analysis, "suggested_summary", "") or ""
    urgency = getattr(analysis, "urgency", "medium")
    draft = (
        "Hi,\n\n"
        "Thanks for reaching out. I saw your message and will address this as soon as possible.\n\n"
        f"Summary: {summary}\n\n"
        "Best,\nYour Email Agent"
    )
    print(f"[AUTO_DRAFT_REPLY] email={email_id} urgency={urgency}\n{draft}")


def suggest_reply_draft(
    email_id: str, original_email_body: str, analysis: EmailAnalysis
) -> None:
    summary = getattr(analysis, "suggested_summary", "") or ""
    draft = (
        "Hi,\n\n"
        "Here’s a suggested reply based on the email:\n\n"
        f"{summary}\n\n"
        "Feel free to edit and send."
    )
    print(f"[SUGGEST_REPLY_DRAFT] email={email_id}\n{draft}")


def summary_only(email_id: str, analysis: EmailAnalysis) -> None:
    summary = getattr(analysis, "suggested_summary", "") or "[no summary]"
    print(f"[SUMMARY] email={email_id} {summary}")


def no_action(email_id: str) -> None:
    print(f"[INFO] No action taken for email={email_id}.")


def execute_actions(
    email_id: str,
    original_email_body: str,
    analysis: EmailAnalysis,
    actions: List[Action],
) -> None:
    """Dispatch execution for each action (stubbed with log lines)."""
    for action in actions:
        if action == "NOTIFY_USER":
            notify_user(email_id, analysis)
        elif action == "CREATE_CALENDAR_EVENT":
            create_calendar_event(email_id, analysis)
        elif action == "AUTO_DRAFT_REPLY":
            auto_draft_reply(email_id, original_email_body, analysis)
        elif action == "SUGGEST_REPLY_DRAFT":
            suggest_reply_draft(email_id, original_email_body, analysis)
        elif action == "SUMMARY_ONLY":
            summary_only(email_id, analysis)
        elif action == "NO_ACTION":
            no_action(email_id)
