# Email Agent API

FastAPI backend for storing and managing email entries for the agent. Uses SQLite by default via SQLModel, with an extensible `Email` data model and REST endpoints.

## Data model
- `Email`: `id`, `subject`, `body`, `from_address`, `to_address`, `status` (`draft|queued|sent|failed`), `tags` (JSON list), `attachments` (list of attachment metadata), `gmail_id`, `thread_id`, `snippet`, `created_at`, `updated_at`.

## Setup
```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the server
```bash
uvicorn app.main:app --reload
```
The API will be available at `http://127.0.0.1:8000` with docs at `/docs`.

## Example requests (local data)
Create:
```bash
curl -X POST http://127.0.0.1:8000/api/emails \
  -H "Content-Type: application/json" \
  -d '{"subject":"Hello","body":"Testing","from_address":"a@example.com","to_address":"b@example.com","status":"draft","tags":["demo"]}'
```

List:
```bash
curl http://127.0.0.1:8000/api/emails
```

Update status:
```bash
curl -X PATCH http://127.0.0.1:8000/api/emails/1 \
  -H "Content-Type: application/json" \
  -d '{"status":"queued"}'
```

## Connect to Gmail
The backend can sync Gmail messages, download attachments, and send replies via Gmail API.

1. Enable Gmail API and create OAuth client:
   - Go to Google Cloud Console → APIs & Services → Credentials.
   - Create OAuth client ID for "Desktop App".
   - Download the client secret JSON and save it to `api/data/google_client_secret.json` (or set env `GOOGLE_CLIENT_SECRET_PATH` to the file path).
   - Enable the Gmail API in the same project.
2. Install deps (see Setup) and generate a token:
   ```bash
   cd api
   source .venv/bin/activate
   python -m app.gmail_auth
   ```
   A browser will open for consent; the OAuth token is stored at `api/data/token.json` for offline access.
3. Sync the latest inbox emails into the DB:
   ```bash
   curl -X POST "http://127.0.0.1:8000/api/gmail/sync?max_results=10&query=in:inbox"
   ```
4. List synced Gmail messages:
   ```bash
   curl http://127.0.0.1:8000/api/gmail/messages
   ```
5. Download an attachment from a synced message (find `gmail_id` and `attachment_id` in the message payload):
   ```bash
   curl "http://127.0.0.1:8000/api/gmail/attachments/{gmail_id}/{attachment_id}"
   ```
6. Send a stored email via Gmail (creates a Gmail send event):
   ```bash
   curl -X POST http://127.0.0.1:8000/api/gmail/send/1
```

### Scopes
The app requests `https://www.googleapis.com/auth/gmail.modify` to read, download attachments, and send messages. Tokens are cached at `api/data/token.json`. If you need a different scope, delete the token file and rerun the auth helper.

## Agent endpoints
- `POST /api/agent/sync_once`: run one full tick (fetch → analyze → actions).
- `GET /api/events?limit=20`: recent processed emails with `intent_actions` and analysis info (used by the desktop app).

## Intent classification (LLM integration scaffold)
- Expected LLM JSON (fields: urgency, importance, action_required, needs_reply, reply_complexity, contains_meeting, meeting_details, email_category, sender_role, notification_recommended, suggested_summary).
- Data structures in `app/intent.py`:
  - `EmailIntentAnalysis` (Pydantic model) and enums for each categorical field.
  - `decide_actions(payload_dict)` → list of actions (`NOTIFY_USER`, `CREATE_CALENDAR_EVENT`, `AUTO_DRAFT_REPLY`, `SUGGEST_REPLY_DRAFT`, `SUMMARY_ONLY`, `NO_ACTION`).
  - `apply_analysis_to_email(email, payload_dict)` → stores the analysis JSON and derived actions on the `Email` record (`intent_analysis`, `intent_actions` columns).
- How to use after you call your LLM:
  ```python
  from app.intent import apply_analysis_to_email
  from app.database import get_session
  from app.models import Email

  # suppose llm_payload is the JSON dict returned by your LLM
  with Session(engine) as session:
      email = session.get(Email, email_id)
      apply_analysis_to_email(email, llm_payload)
      session.add(email)
      session.commit()
  ```
  This validates the payload, derives actions, and persists them for downstream steps (notifications, calendar event creation, auto-draft generation).

## Desktop app (Electron)
Located in `desktop/`. Minimal tray + window that starts the backend/agent, polls events, and shows notifications.

Quick start:
```bash
cd "/Users/nakshatragajbhiye/Email Agent"
cd desktop
npm install
# Ensure the Python backend venv is set up and GEMINI_API_KEY is in env
npm start
```
The Electron app:
- Spawns uvicorn on port 8001 and the agent runner.
- Tray menu: open dashboard, sync now, start/stop agent, quit.
- Dashboard: simple event viewer and links to API docs.
