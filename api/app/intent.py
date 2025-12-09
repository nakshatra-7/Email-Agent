from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .models import Email


class Urgency(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Importance(str, Enum):
    important = "important"
    normal = "normal"
    trivial = "trivial"


class ReplyComplexity(str, Enum):
    none = "none"
    simple = "simple"
    complex = "complex"


class EmailCategory(str, Enum):
    academic = "academic"
    work = "work"
    finance = "finance"
    social = "social"
    marketing = "marketing"
    notification = "notification"
    spam = "spam"
    other = "other"


class SenderRole(str, Enum):
    manager = "manager"
    professor = "professor"
    recruiter = "recruiter"
    friend = "friend"
    service = "service"
    unknown = "unknown"


class MeetingDetails(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD
    start_time: Optional[str] = Field(None, alias="start_time")  # HH:MM
    end_time: Optional[str] = Field(None, alias="end_time")  # HH:MM
    timezone: Optional[str] = None
    location: Optional[str] = None
    online_meeting_link: Optional[str] = None

    @validator("date")
    def _empty_to_none(cls, v: Optional[str]) -> Optional[str]:
        return v or None


class EmailIntentAnalysis(BaseModel):
    urgency: Urgency
    importance: Importance
    action_required: bool
    needs_reply: bool
    reply_complexity: ReplyComplexity
    contains_meeting: bool
    meeting_details: MeetingDetails
    email_category: EmailCategory
    sender_role: SenderRole
    notification_recommended: bool
    suggested_summary: str


class Action(str, Enum):
    notify_user = "NOTIFY_USER"
    create_calendar_event = "CREATE_CALENDAR_EVENT"
    auto_draft_reply = "AUTO_DRAFT_REPLY"
    suggest_reply_draft = "SUGGEST_REPLY_DRAFT"
    summary_only = "SUMMARY_ONLY"
    no_action = "NO_ACTION"


def decide_actions(email_analysis: Dict) -> List[Action]:
    """
    Convert raw LLM intent analysis into a list of actions for the agent.

    Accepts a dict so it works directly with LLM JSON output; it is validated
    by EmailIntentAnalysis for safety.
    """
    parsed = EmailIntentAnalysis.parse_obj(email_analysis)
    actions: List[Action] = []

    # 1. Notifications
    if parsed.urgency in [Urgency.critical, Urgency.high] and parsed.notification_recommended:
        actions.append(Action.notify_user)

    # 2. Calendar
    if parsed.contains_meeting:
        actions.append(Action.create_calendar_event)

    # 3. Replies
    if parsed.needs_reply and parsed.action_required:
        if parsed.reply_complexity == ReplyComplexity.simple:
            actions.append(Action.auto_draft_reply)
        elif parsed.reply_complexity == ReplyComplexity.complex:
            actions.append(Action.suggest_reply_draft)

    # 4. Low-value stuff
    if (
        parsed.urgency == Urgency.low
        and parsed.email_category in [EmailCategory.marketing, EmailCategory.notification]
    ):
        actions.append(Action.summary_only)

    if not actions:
        actions.append(Action.no_action)

    return actions


def apply_analysis_to_email(email: Email, analysis_payload: Dict) -> Email:
    """
    Persist analysis + actions to an Email record.

    Returns the mutated email (caller should commit/refresh if needed).
    """
    actions = decide_actions(analysis_payload)
    email.intent_analysis = analysis_payload
    email.intent_actions = [a.value for a in actions]
    return email
