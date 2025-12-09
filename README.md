# Email Agent

FastAPI + Gmail + Gemini–powered agent that:
- Syncs Gmail inbox (read, attachments, send).
- Runs LLM intent analysis (urgency, reply needs, meetings, category, summary).
- Maps analysis to actions (notify, calendar, auto/suggested replies, summaries).
- Polls on a schedule and marks emails processed.
- Electron desktop companion for tray controls, notifications, and a minimal dashboard.

## What the project does
- Gmail ingest: pull unread inbox, store metadata, snippet/body, attachment info, Gmail IDs.
- LLM understanding: pass email (plus PDF text) to Gemini; get urgency, importance, needs reply, reply complexity, meeting details, category, sender role, notification recommendation, and a summary.
- Policy engine: converts the LLM analysis into actions (notify, create calendar event, auto/suggest reply, summarize only, or no action) with special handling for recruiters, professors/academic emails, marketing/spam, and urgency.
- Actions (current): log notifications, meeting info, summaries, and prepared reply drafts (printed, not sent). Sending can be wired into `actions.py` later.
- Scheduler: background loop periodically fetches, analyzes, acts, and marks emails processed so they’re not re-run.
- Attachments: PDFs are downloaded, text-extracted, and appended to the analysis context; an excerpt is shown in the dashboard.
- Desktop app: Electron wrapper that starts/stops backend + agent, shows notifications, and a dashboard with urgency colors, summaries, meetings, attachment info, and prepared replies.

## Architectureg
- **Backend:** FastAPI, SQLModel/SQLite, Gmail API client, Gemini client.
- **LLM:** Google Gemini (`google-generativeai`), configurable model via `GEMINI_MODEL_NAME`.
- **Scheduler:** Python loop (`app/services/agent_runner.py`) polling Gmail and running analysis/actions.
- **Desktop app:** Electron (`desktop/`) that starts backend/agent, shows notifications, and a dashboard.
- **Data model:** Email table stores headers/body, attachments, Gmail IDs, intent analysis/actions, processed flags, timestamps.

## Prerequisites
- Python 3.11+
- Node.js (for Electron app)
- Gmail OAuth client secret JSON (Desktop app type) → save as `api/data/google_client_secret.json`
- Google Gemini API key (`GEMINI_API_KEY`)

## Backend setup
```bash
cd "Email Agent/api"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Gmail OAuth token
```bash
cd "Email Agent/api"
source .venv/bin/activate
python -m app.gmail_auth  # browser opens, sign in; token saved to data/token.json
```

### Env vars
```bash
export GEMINI_API_KEY="your-gemini-key"
# optional overrides
# export GEMINI_MODEL_NAME="models/gemini-flash-latest"
# export AGENT_POLL_SECONDS=900
# export AGENT_FETCH_LIMIT=10
# export AGENT_GMAIL_QUERY="is:unread in:inbox"
```

### Run FastAPI
```bash
cd "Email Agent/api"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```
- Docs: http://127.0.0.1:8001/docs

### Core endpoints
- `POST /api/gmail/sync` – sync inbox to DB
- `GET /api/gmail/messages` – list stored emails
- `GET /api/gmail/attachments/{gmail_id}/{attachment_id}` – download attachment
- `POST /api/gmail/send/{email_id}` – send a stored email via Gmail
- `POST /api/gmail/analyze/{email_id}` – run LLM analysis, store actions
- `POST /api/agent/sync_once` – one full tick (fetch → analyze → act)
- `GET /api/agent/events?limit=20` – recent processed emails/actions (dashboard feed)

## Agent (scheduler)
- File: `api/app/services/agent_runner.py`
- Uses env `AGENT_POLL_SECONDS` (default 900s) and `AGENT_FETCH_LIMIT`.
- Runs: `python -m app.services.agent_runner`
- Tick: sync Gmail → add PDF text → LLM analysis → decide_actions → execute_actions (prints/logs) → mark processed.

## Electron desktop app
Minimal tray + dashboard with notifications and a card UI (urgency colors, summary, meeting info, attachment summary, prepared reply).

Setup & run:
```bash
cd "Email Agent/desktop"
npm install
# ensure backend venv deps installed and GEMINI_API_KEY set in env
npm start
```
- Tray menu: Open dashboard, Sync now, Start/Stop agent, Quit.
- Polls `/api/agent/events` and shows notifications for new emails and high/critical urgency.
- Dashboard view: shows From, Subject, urgency badge (red=high/critical, yellow=medium, green=low), summary, meeting details, attachment count and excerpt, and prepared reply text when applicable.
- Notifications: fires on new processed emails, and for high/critical urgency or explicit NOTIFY_USER actions; meeting reminders are surfaced via notifications when present.

## Notes / limits
- Auto-reply is printed/shown; not actually sent. Add sending logic in `actions.py` if needed.
- PDF text extraction is best-effort (no OCR); only PDFs are summarized.
- Gemini free-tier quotas may throttle frequent syncs; lower fetch limits/poll rate or use a model/quota with headroom.

## Project layout
- `api/app/main.py` – FastAPI entry
- `api/app/models.py` – SQLModel schemas
- `api/app/gmail_client.py` – Gmail API helpers
- `api/app/routers/` – API routes (gmail, emails, agent)
- `api/app/services/` – LLM, actions, scheduler, attachment text
- `desktop/` – Electron app (main.js, index.html, preload.js, package.json)

## Quick start (dev)
1) Install backend deps, set envs, run `uvicorn app.main:app --port 8001`.
2) Run agent loop separately (`python -m app.services.agent_runner`) or use desktop “Sync now.”
3) Run Electron app from `desktop/` with `npm start`.
