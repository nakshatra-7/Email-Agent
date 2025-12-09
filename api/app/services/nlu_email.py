import json
import os
from typing import Any, Dict

import google.generativeai as genai
from pydantic import BaseModel, Field

# Pydantic models describing the expected LLM output
class MeetingDetails(BaseModel):
    title: str | None = None
    date: str | None = None  # YYYY-MM-DD
    start_time: str | None = None  # HH:MM
    end_time: str | None = None  # HH:MM
    timezone: str | None = None
    location: str | None = None
    online_meeting_link: str | None = None


class EmailAnalysis(BaseModel):
    urgency: str = "medium"
    importance: str = "normal"
    action_required: bool = False
    needs_reply: bool = False
    reply_complexity: str = "none"
    contains_meeting: bool = False
    meeting_details: MeetingDetails = Field(default_factory=MeetingDetails)
    email_category: str = "other"
    sender_role: str = "unknown"
    notification_recommended: bool = False
    suggested_summary: str = ""


def _configure_gemini_client() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY environment variable for Gemini client."
        )
    genai.configure(api_key=api_key)


def build_email_analysis_system_prompt() -> str:
    """Instruction prompt to drive Gemini for email intent analysis."""
    return (
        "You are an email analysis assistant. "
        "Given an email subject, sender, and body, you must output ONLY JSON following this exact schema:\n"
        "{\n"
        '  "urgency": "critical | high | medium | low",\n'
        '  "importance": "important | normal | trivial",\n'
        '  "action_required": true or false,\n'
        '  "needs_reply": true or false,\n'
        '  "reply_complexity": "none | simple | complex",\n'
        '  "contains_meeting": true or false,\n'
        '  "meeting_details": {\n'
        '    "title": string or null,\n'
        '    "date": "YYYY-MM-DD" or null,\n'
        '    "start_time": "HH:MM" or null,\n'
        '    "end_time": "HH:MM" or null,\n'
        '    "timezone": string or null,\n'
        '    "location": string or null,\n'
        '    "online_meeting_link": string or null\n'
        "  },\n"
        '  "email_category": "academic | work | finance | social | marketing | notification | spam | other",\n'
        '  "sender_role": "manager | professor | recruiter | friend | service | unknown",\n'
        '  "notification_recommended": true or false,\n'
        '  "suggested_summary": string\n'
        "}\n"
        "Guidelines:\n"
        "- Assess urgency and importance from tone, sender, and deadlines.\n"
        "- Decide if action is required and if a reply is needed; set reply_complexity accordingly.\n"
        "- Detect meeting/event details if present and populate meeting_details.\n"
        "- Categorize the email and infer sender_role.\n"
        "- Recommend notification for high-urgency items.\n"
        "- Provide a concise suggested_summary.\n"
        "Respond with JSON only—no extra text."
    )


def _parse_llm_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse LLM JSON: {exc}") from exc


def _extract_text(response: Any) -> str:
    """
    Extract response text from Gemini result. Prefer .text, otherwise stitch
    candidate parts that are strings.
    """
    if getattr(response, "text", None):
        return response.text
    # Fallback: iterate candidates/parts
    candidates = getattr(response, "candidates", []) or []
    for cand in candidates:
        parts = getattr(getattr(cand, "content", None), "parts", []) or []
        texts = [p.text for p in parts if hasattr(p, "text")]
        if texts:
            return "\n".join(texts)
    return ""


def _fill_defaults(payload: Dict[str, Any]) -> EmailAnalysis:
    """Apply defaults for any missing fields and build EmailAnalysis."""
    meeting_payload = payload.get("meeting_details") or {}
    meeting = MeetingDetails(**meeting_payload)

    return EmailAnalysis(
        urgency=payload.get("urgency", "medium"),
        importance=payload.get("importance", "normal"),
        action_required=bool(payload.get("action_required", False)),
        needs_reply=bool(payload.get("needs_reply", False)),
        reply_complexity=payload.get("reply_complexity", "none"),
        contains_meeting=bool(payload.get("contains_meeting", False)),
        meeting_details=meeting,
        email_category=payload.get("email_category", "other"),
        sender_role=payload.get("sender_role", "unknown"),
        notification_recommended=bool(payload.get("notification_recommended", False)),
        suggested_summary=payload.get("suggested_summary", ""),
    )


def analyze_email_with_llm(subject: str, sender: str, body: str) -> EmailAnalysis:
    """
    Call Gemini to analyze an email and return structured EmailAnalysis.

    Raises:
        RuntimeError: if GEMINI_API_KEY is missing or Gemini call fails.
        ValueError: if the LLM response cannot be parsed as JSON.
    """
    _configure_gemini_client()

    system_prompt = build_email_analysis_system_prompt()
    email_text = f"Subject: {subject}\nFrom: {sender}\n\nBody:\n{body}"

    # Default to a broadly available model; allow override via env.
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
        generation_config={
            # Force JSON-only output.
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )

    try:
        response = model.generate_content(email_text)
    except Exception as exc:  # pragma: no cover - transport errors
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

    text = _extract_text(response)
    if not text:
        raise ValueError("Empty response from Gemini (no text).")

    payload = _parse_llm_json(text)
    return _fill_defaults(payload)
