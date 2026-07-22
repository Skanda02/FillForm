# FillForm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend FillForm with profile management, eligibility checking, Google Calendar integration, and browser-based form auto-fill.

**Architecture:** Modular Flask services — profile, eligibility, calendar, autofill — each in its own file. MongoDB replaces SQLite for profiles/calendar tokens. Submissions remain in SQLite. Frontend adds profile UI and eligibility display.

**Tech Stack:** Flask, pymongo, selenium, google-api-python-client, google-auth-oauthlib, HTML/CSS/JS (no framework)

## Global Constraints

- Python 3.11+, Flask 3.0+
- MongoDB running locally on default port 27017
- Google Calendar API credentials in `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- No auto-submit under any circumstances — user always confirms submission manually
- All new files follow existing code style: `from __future__ import annotations`, type hints, no comments unless requested

---

## Skanda's Tasks: Backend Services

### Task 1: MongoDB Connection & Config

**Files:**
- Create: `backend/database.py`
- Modify: `backend/config.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `MONGO_URI` env var (default `mongodb://localhost:27017`)
- Produces: `get_db()` → pymongo Database, `get_collection(name)` → Collection

- [ ] **Step 1: Add pymongo to requirements.txt**

```
pymongo>=4.6.0
```

- [ ] **Step 2: Run pip install**

```bash
pip install pymongo>=4.6.0
```

- [ ] **Step 3: Create backend/database.py**

```python
"""MongoDB connection for FillForm."""

from __future__ import annotations

import os
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(uri)
        _db = _client["fillform"]
    return _db


def get_collection(name: str) -> Collection:
    return get_db()[name]
```

- [ ] **Step 4: Add MongoDB config helper to config.py**

Append to `backend/config.py`:

```python
def get_mongo_uri() -> str:
    return os.environ.get("MONGO_URI", "mongodb://localhost:27017")

def get_google_client_id() -> str | None:
    return os.environ.get("GOOGLE_CLIENT_ID")

def get_google_client_secret() -> str | None:
    return os.environ.get("GOOGLE_CLIENT_SECRET")
```

- [ ] **Step 5: Update .env with template keys**

Append to `.env`:

```
MONGO_URI=mongodb://localhost:27017
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

- [ ] **Step 6: Verify MongoDB connection**

```bash
python -c "from backend.database import get_db; db = get_db(); print(db.list_collection_names())"
```

Expected: `[]` (empty list, database exists)

- [ ] **Step 7: Commit**

```bash
git add backend/database.py backend/config.py requirements.txt .env
git commit -m "feat: add MongoDB connection and config helpers"
```

---

### Task 2: Profile Service

**Files:**
- Create: `backend/services/profile_service.py`
- Modify: `backend/routes/api.py`

**Interfaces:**
- Consumes: `get_collection("profiles")` from `backend/database.py`
- Produces: `create_or_update_profile(data)` → dict, `get_profile(profile_id)` → dict | None, `get_default_profile()` → dict | None, `delete_profile(profile_id)` → bool

- [ ] **Step 1: Create backend/services/profile_service.py**

```python
"""Profile management service for FillForm."""

from __future__ import annotations

from datetime import datetime, timezone
from bson import ObjectId
from backend.database import get_collection


def _serialize(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


def create_or_update_profile(data: dict, profile_id: str | None = None) -> dict:
    col = get_collection("profiles")
    now = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = now

    if profile_id:
        col.update_one({"_id": ObjectId(profile_id)}, {"$set": data}, upsert=True)
        return get_profile(profile_id)

    data["created_at"] = now
    result = col.insert_one(data)
    return get_profile(str(result.inserted_id))


def get_profile(profile_id: str) -> dict | None:
    col = get_collection("profiles")
    doc = col.find_one({"_id": ObjectId(profile_id)})
    return _serialize(doc)


def get_default_profile() -> dict | None:
    col = get_collection("profiles")
    doc = col.find_one(sort=[("created_at", -1)])
    return _serialize(doc)


def delete_profile(profile_id: str) -> bool:
    col = get_collection("profiles")
    result = col.delete_one({"_id": ObjectId(profile_id)})
    return result.deleted_count > 0


def list_profiles() -> list[dict]:
    col = get_collection("profiles")
    return [_serialize(doc) for doc in col.find(sort=[("created_at", -1)])]
```

- [ ] **Step 2: Add profile API routes to api.py**

Append these routes to `backend/routes/api.py`:

```python
from backend.services.profile_service import (
    create_or_update_profile,
    get_profile,
    get_default_profile,
    delete_profile,
    list_profiles,
)


@api_bp.get("/api/profiles")
def api_list_profiles() -> tuple[object, int]:
    return jsonify(list_profiles()), 200


@api_bp.get("/api/profiles/<profile_id>")
def api_get_profile(profile_id: str) -> tuple[object, int]:
    profile = get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile), 200


@api_bp.get("/api/profiles/default")
def api_get_default_profile() -> tuple[object, int]:
    profile = get_default_profile()
    if not profile:
        return jsonify({"error": "No profile found"}), 404
    return jsonify(profile), 200


@api_bp.post("/api/profiles")
def api_create_profile() -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    profile = create_or_update_profile(data)
    return jsonify(profile), 201


@api_bp.put("/api/profiles/<profile_id>")
def api_update_profile(profile_id: str) -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    profile = create_or_update_profile(data, profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile), 200


@api_bp.delete("/api/profiles/<profile_id>")
def api_delete_profile(profile_id: str) -> tuple[object, int]:
    deleted = delete_profile(profile_id)
    if not deleted:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"success": True}), 200
```

- [ ] **Step 3: Test profile endpoints manually**

Start the app and test:

```bash
# Create profile
curl -X POST http://127.0.0.1:5000/api/profiles \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","phone":"1234567890","college":"ABC College","usn":"1AB20CS001","branch":"CSE","degree":"B.E.","graduation_year":2026,"overall_cgpa":8.5}'

# List profiles
curl http://127.0.0.1:5000/api/profiles
```

Expected: JSON with profile data including `id` field

- [ ] **Step 4: Commit**

```bash
git add backend/services/profile_service.py backend/routes/api.py
git commit -m "feat: add profile service and API endpoints"
```

---

### Task 3: Eligibility Service

**Files:**
- Create: `backend/services/eligibility_service.py`
- Modify: `backend/routes/api.py`

**Interfaces:**
- Consumes: `get_submission(id)` from `database/models.py`, `get_profile(id)` from `profile_service.py`
- Produces: `check_eligibility(submission_id, profile_id)` → dict with `eligible: bool`, `reasons: list[str]`

- [ ] **Step 1: Create backend/services/eligibility_service.py**

```python
"""Eligibility checking service for FillForm."""

from __future__ import annotations

import re
from database.models import get_submission
from backend.services.profile_service import get_profile


def _parse_percentage(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(match.group(1)) if match else None


def check_eligibility(submission_id: int, profile_id: str) -> dict:
    submission = get_submission(submission_id)
    if not submission:
        return {"eligible": False, "reasons": ["Submission not found"], "checked": False}

    profile = get_profile(profile_id)
    if not profile:
        return {"eligible": False, "reasons": ["Profile not found"], "checked": False}

    reasons = []
    eligible = True

    extracted = submission.get("keywords", {})
    if isinstance(extracted, dict):
        pass
    text = submission.get("text", "")

    batch_match = re.search(r"(?:batch|year)\s*[:=]?\s*(\d{4})", text, re.IGNORECASE)
    if batch_match:
        required_batch = batch_match.group(1)
        grad_year = str(profile.get("graduation_year", ""))
        if grad_year and required_batch not in grad_year:
            eligible = False
            reasons.append(f"Batch mismatch: requires {required_batch}, you are {grad_year}")

    branches_match = re.search(r"(?:branches?|departments?)\s*[:=]?\s*([^\n]+)", text, re.IGNORECASE)
    if branches_match:
        required_branches = [b.strip().upper() for b in branches_match.group(1).split(",")]
        user_branch = (profile.get("branch") or "").upper()
        if user_branch and required_branches and user_branch not in required_branches:
            eligible = False
            reasons.append(f"Branch mismatch: requires {', '.join(required_branches)}, you are {user_branch}")

    degree_match = re.search(r"(?:degree|qualification)\s*[:=]?\s*(\w[\w\s]*)", text, re.IGNORECASE)
    if degree_match:
        required_degree = degree_match.group(1).strip().upper()
        user_degree = (profile.get("degree") or "").upper()
        if user_degree and required_degree and required_degree not in user_degree:
            eligible = False
            reasons.append(f"Degree mismatch: requires {required_degree}, you have {user_degree}")

    pct_match = re.search(r"(?:percentage|cgpa|gpa)\s*[>=]+\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if pct_match:
        required_pct = float(pct_match.group(1))
        user_cgpa = profile.get("overall_cgpa")
        if user_cgpa is not None:
            user_pct = float(user_cgpa) if float(user_cgpa) <= 10 else float(user_cgpa)
            if user_pct < required_pct:
                eligible = False
                reasons.append(f"CGPA below minimum: {user_pct} < {required_pct}")

    backlog_match = re.search(r"(?:no\s+backlog|active\s+backlog|backlog\s*[=:]\s*(\d+))", text, re.IGNORECASE)
    if backlog_match:
        rule = backlog_match.group(0).lower()
        if "no backlog" in rule:
            active_backlogs = profile.get("active_backlogs", 0)
            if active_backlogs and int(active_backlogs) > 0:
                eligible = False
                reasons.append(f"Active backlogs: {active_backlogs}")

    return {
        "eligible": eligible,
        "reasons": reasons if reasons else ["All criteria met"],
        "checked": True,
    }
```

- [ ] **Step 2: Add eligibility API route to api.py**

Append to `backend/routes/api.py`:

```python
from backend.services.eligibility_service import check_eligibility


@api_bp.post("/api/check-eligibility")
def api_check_eligibility() -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    submission_id = data.get("submission_id")
    profile_id = data.get("profile_id")

    if not submission_id or not profile_id:
        return jsonify({"error": "submission_id and profile_id required"}), 400

    result = check_eligibility(int(submission_id), profile_id)
    return jsonify(result), 200
```

- [ ] **Step 3: Test eligibility endpoint**

```bash
# First create a profile and submission, then:
curl -X POST http://127.0.0.1:5000/api/check-eligibility \
  -H "Content-Type: application/json" \
  -d '{"submission_id": 1, "profile_id": "<your_profile_id>"}'
```

Expected: JSON with `eligible`, `reasons`, `checked` fields

- [ ] **Step 4: Commit**

```bash
git add backend/services/eligibility_service.py backend/routes/api.py
git commit -m "feat: add eligibility checking service and API"
```

---

### Task 4: Calendar Service

**Files:**
- Create: `backend/services/calendar_service.py`
- Modify: `backend/routes/api.py`
- Modify: `.env`

**Interfaces:**
- Consumes: `get_collection("calendar_tokens")` from `backend/database.py`, Google OAuth2 credentials
- Produces: `get_auth_url()` → str, `handle_callback(code, profile_id)` → bool, `create_event(profile_id, event_data)` → dict | None, `is_connected(profile_id)` → bool

- [ ] **Step 1: Add google API packages to requirements.txt**

Append to `requirements.txt`:

```
google-api-python-client>=2.110.0
google-auth-httplib2>=0.1.1
google-auth-oauthlib>=1.1.0
```

- [ ] **Step 2: Install packages**

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

- [ ] **Step 3: Create backend/services/calendar_service.py**

```python
"""Google Calendar integration service for FillForm."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from backend.database import get_collection


SCOPES = ["https://www.googleapis.com/auth/calendar"]
REDIRECT_URI = "http://127.0.0.1:5000/api/calendar/callback"


def _get_client_config() -> dict:
    return {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }


def get_auth_url(state: str) -> str:
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return auth_url


def handle_callback(code: str, profile_id: str) -> bool:
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    col = get_collection("calendar_tokens")
    col.update_one(
        {"profile_id": profile_id},
        {
            "$set": {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {
                "profile_id": profile_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )
    return True


def _get_credentials(profile_id: str) -> Credentials | None:
    col = get_collection("calendar_tokens")
    doc = col.find_one({"profile_id": profile_id})
    if not doc:
        return None
    return Credentials(
        token=doc.get("access_token"),
        refresh_token=doc.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        scopes=SCOPES,
    )


def is_connected(profile_id: str) -> bool:
    return _get_credentials(profile_id) is not None


def create_event(profile_id: str, event_data: dict) -> dict | None:
    creds = _get_credentials(profile_id)
    if not creds:
        return None

    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": event_data.get("summary", "FillForm Reminder"),
        "description": event_data.get("description", ""),
        "start": {
            "dateTime": event_data["start_datetime"],
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": event_data["end_datetime"],
            "timeZone": "Asia/Kolkata",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 7 * 24 * 60},
                {"method": "popup", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ],
        },
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    return {"event_id": created.get("id"), "html_link": created.get("htmlLink")}
```

- [ ] **Step 4: Add calendar API routes to api.py**

Append to `backend/routes/api.py`:

```python
import secrets
from backend.services.calendar_service import get_auth_url, handle_callback, create_event, is_connected
from flask import redirect


@api_bp.get("/api/calendar/auth")
def api_calendar_auth() -> tuple[object, int]:
    profile_id = request.args.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    state = secrets.token_urlsafe(32)
    auth_url = get_auth_url(state)
    return jsonify({"auth_url": auth_url}), 200


@api_bp.get("/api/calendar/callback")
def api_calendar_callback() -> tuple[object, int]:
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return jsonify({"error": "Authorization code not provided"}), 400
    handle_callback(code, state)
    return redirect("http://127.0.0.1:5000")


@api_bp.post("/api/calendar/create-event")
def api_calendar_create_event() -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    profile_id = data.get("profile_id")
    event_data = data.get("event_data")

    if not profile_id or not event_data:
        return jsonify({"error": "profile_id and event_data required"}), 400

    result = create_event(profile_id, event_data)
    if not result:
        return jsonify({"error": "Calendar not connected"}), 400
    return jsonify(result), 201


@api_bp.get("/api/calendar/status")
def api_calendar_status() -> tuple[object, int]:
    profile_id = request.args.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    return jsonify({"connected": is_connected(profile_id)}), 200
```

- [ ] **Step 5: Test calendar auth flow**

```bash
curl "http://127.0.0.1:5000/api/calendar/auth?profile_id=test123"
```

Expected: JSON with `auth_url` containing Google OAuth URL

- [ ] **Step 6: Commit**

```bash
git add backend/services/calendar_service.py backend/routes/api.py requirements.txt .env
git commit -m "feat: add Google Calendar OAuth2 integration"
```

---

## Manvitha's Tasks: Frontend + Auto-fill

### Task 5: Profile Management UI

**Files:**
- Modify: `frontend/index.html`

**Interfaces:**
- Consumes: `GET /api/profiles`, `POST /api/profiles`, `PUT /api/profiles/<id>`, `GET /api/profiles/default`
- Produces: Profile form UI, profile display section

- [ ] **Step 1: Add profile section to index.html**

Add after the `<section class="panel grid">` closing tag and before the `<pre>` tag in `frontend/index.html`:

```html
<section class="panel" id="profile-panel" style="margin-top: 24px;">
  <h2>Your Profile</h2>
  <p class="subtle">Fill in your details once. The system will use them for eligibility checks and form auto-fill.</p>
  <div id="profile-display" style="display: none;">
    <div class="result-grid">
      <div class="result-card">
        <span class="result-label">Name</span>
        <div class="result-value" id="profile-name">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">Email</span>
        <div class="result-value" id="profile-email">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">Phone</span>
        <div class="result-value" id="profile-phone">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">College</span>
        <div class="result-value" id="profile-college">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">USN</span>
        <div class="result-value" id="profile-usn">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">Branch</span>
        <div class="result-value" id="profile-branch">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">Degree</span>
        <div class="result-value" id="profile-degree">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">CGPA</span>
        <div class="result-value" id="profile-cgpa">-</div>
      </div>
      <div class="result-card">
        <span class="result-label">Skills</span>
        <div class="result-value" id="profile-skills">-</div>
      </div>
    </div>
    <button id="edit-profile-btn" style="margin-top: 16px;">Edit Profile</button>
    <button id="calendar-connect-btn" style="margin-top: 16px; margin-left: 8px; background: #4285f4;">Connect Google Calendar</button>
  </div>
  <div id="profile-form" style="display: none;">
    <div class="grid" style="grid-template-columns: 1fr 1fr;">
      <div>
        <label for="pf-name">Full Name *</label>
        <input type="text" id="pf-name" placeholder="John Doe" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-email">Email *</label>
        <input type="email" id="pf-email" placeholder="john@example.com" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-phone">Phone *</label>
        <input type="tel" id="pf-phone" placeholder="+91-9876543210" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-college">College *</label>
        <input type="text" id="pf-college" placeholder="ABC Engineering College" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-usn">USN *</label>
        <input type="text" id="pf-usn" placeholder="1AB20CS001" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-branch">Branch *</label>
        <input type="text" id="pf-branch" placeholder="CSE" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-degree">Degree</label>
        <input type="text" id="pf-degree" placeholder="B.E." style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-graduation-year">Graduation Year</label>
        <input type="number" id="pf-graduation-year" placeholder="2026" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-tenth">10th Marks</label>
        <input type="text" id="pf-tenth" placeholder="95%" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-puc">PUC Marks</label>
        <input type="text" id="pf-puc" placeholder="92%" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-cgpa">Overall CGPA</label>
        <input type="number" step="0.01" id="pf-cgpa" placeholder="8.75" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
      <div>
        <label for="pf-backlogs">Active Backlogs</label>
        <input type="number" id="pf-backlogs" placeholder="0" value="0" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
      </div>
    </div>
    <div style="margin-top: 16px;">
      <label for="pf-skills">Skills (comma-separated)</label>
      <input type="text" id="pf-skills" placeholder="Python, JavaScript, React" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
    </div>
    <div style="margin-top: 16px;">
      <label for="pf-interests">Interests (comma-separated)</label>
      <input type="text" id="pf-interests" placeholder="web development, AI/ML" style="width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db;">
    </div>
    <button id="save-profile-btn" style="margin-top: 16px;">Save Profile</button>
    <button id="cancel-profile-btn" style="margin-top: 16px; margin-left: 8px; background: #6b7280;">Cancel</button>
  </div>
</section>
```

- [ ] **Step 2: Add profile JavaScript to index.html**

Add before the closing `</script>` tag in `frontend/index.html`:

```javascript
// Profile Management
let currentProfileId = null;
const profileDisplay = document.getElementById('profile-display');
const profileForm = document.getElementById('profile-form');
const editProfileBtn = document.getElementById('edit-profile-btn');
const saveProfileBtn = document.getElementById('save-profile-btn');
const cancelProfileBtn = document.getElementById('cancel-profile-btn');
const calendarConnectBtn = document.getElementById('calendar-connect-btn');

const profileFields = ['name', 'email', 'phone', 'college', 'usn', 'branch', 'degree', 'cgpa', 'skills'];

function populateProfileForm(profile) {
  document.getElementById('pf-name').value = profile.name || '';
  document.getElementById('pf-email').value = profile.email || '';
  document.getElementById('pf-phone').value = profile.phone || '';
  document.getElementById('pf-college').value = profile.college || '';
  document.getElementById('pf-usn').value = profile.usn || '';
  document.getElementById('pf-branch').value = profile.branch || '';
  document.getElementById('pf-degree').value = profile.degree || '';
  document.getElementById('pf-graduation-year').value = profile.graduation_year || '';
  document.getElementById('pf-tenth').value = profile.tenth_marks || '';
  document.getElementById('pf-puc').value = profile.puc_marks || '';
  document.getElementById('pf-cgpa').value = profile.overall_cgpa || '';
  document.getElementById('pf-backlogs').value = profile.active_backlogs || 0;
  document.getElementById('pf-skills').value = (profile.skills || []).join(', ');
  document.getElementById('pf-interests').value = (profile.interests || []).join(', ');
}

function renderProfileDisplay(profile) {
  document.getElementById('profile-name').textContent = profile.name || '-';
  document.getElementById('profile-email').textContent = profile.email || '-';
  document.getElementById('profile-phone').textContent = profile.phone || '-';
  document.getElementById('profile-college').textContent = profile.college || '-';
  document.getElementById('profile-usn').textContent = profile.usn || '-';
  document.getElementById('profile-branch').textContent = profile.branch || '-';
  document.getElementById('profile-degree').textContent = profile.degree || '-';
  document.getElementById('profile-cgpa').textContent = profile.overall_cgpa || '-';
  document.getElementById('profile-skills').textContent = (profile.skills || []).join(', ') || '-';
}

async function loadProfile() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/profiles/default`);
    if (response.ok) {
      const profile = await response.json();
      currentProfileId = profile.id;
      renderProfileDisplay(profile);
      profileDisplay.style.display = 'block';
      profileForm.style.display = 'none';
    } else {
      profileDisplay.style.display = 'none';
      profileForm.style.display = 'block';
    }
  } catch (e) {
    profileDisplay.style.display = 'none';
    profileForm.style.display = 'block';
  }
}

editProfileBtn.addEventListener('click', async () => {
  if (currentProfileId) {
    const response = await fetch(`${API_BASE_URL}/api/profiles/${currentProfileId}`);
    if (response.ok) {
      const profile = await response.json();
      populateProfileForm(profile);
    }
  }
  profileDisplay.style.display = 'none';
  profileForm.style.display = 'block';
});

cancelProfileBtn.addEventListener('click', () => {
  if (currentProfileId) {
    profileDisplay.style.display = 'block';
    profileForm.style.display = 'none';
  } else {
    profileForm.style.display = 'none';
  }
});

saveProfileBtn.addEventListener('click', async () => {
  const data = {
    name: document.getElementById('pf-name').value,
    email: document.getElementById('pf-email').value,
    phone: document.getElementById('pf-phone').value,
    college: document.getElementById('pf-college').value,
    usn: document.getElementById('pf-usn').value,
    branch: document.getElementById('pf-branch').value,
    degree: document.getElementById('pf-degree').value,
    graduation_year: parseInt(document.getElementById('pf-graduation-year').value) || null,
    tenth_marks: document.getElementById('pf-tenth').value,
    puc_marks: document.getElementById('pf-puc').value,
    overall_cgpa: parseFloat(document.getElementById('pf-cgpa').value) || null,
    active_backlogs: parseInt(document.getElementById('pf-backlogs').value) || 0,
    skills: document.getElementById('pf-skills').value.split(',').map(s => s.trim()).filter(Boolean),
    interests: document.getElementById('pf-interests').value.split(',').map(s => s.trim()).filter(Boolean),
  };

  try {
    const url = currentProfileId
      ? `${API_BASE_URL}/api/profiles/${currentProfileId}`
      : `${API_BASE_URL}/api/profiles`;
    const method = currentProfileId ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (response.ok) {
      const profile = await response.json();
      currentProfileId = profile.id;
      renderProfileDisplay(profile);
      profileDisplay.style.display = 'block';
      profileForm.style.display = 'none';
    }
  } catch (e) {
    alert('Failed to save profile');
  }
});

calendarConnectBtn.addEventListener('click', async () => {
  if (!currentProfileId) {
    alert('Please save your profile first');
    return;
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/calendar/auth?profile_id=${currentProfileId}`);
    const data = await response.json();
    if (data.auth_url) {
      window.location.href = data.auth_url;
    }
  } catch (e) {
    alert('Failed to connect to Google Calendar');
  }
});

loadProfile();
```

- [ ] **Step 3: Test profile UI**

Open `http://127.0.0.1:5000`, fill in the profile form, click Save. Verify the profile displays correctly.

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add profile management UI"
```

---

### Task 6: Auto-fill Service

**Files:**
- Create: `backend/services/autofill_service.py`
- Modify: `backend/routes/api.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `get_profile(id)` from `profile_service.py`, Selenium WebDriver
- Produces: `start_autofill(url, profile_id)` → dict, `fill_fields(profile_id)` → dict, `get_form_state()` → dict

- [ ] **Step 1: Add selenium to requirements.txt**

Append to `requirements.txt`:

```
selenium>=4.15.0
```

- [ ] **Step 2: Install selenium**

```bash
pip install selenium>=4.15.0
```

- [ ] **Step 3: Create backend/services/autofill_service.py**

```python
"""Browser auto-fill service for FillForm."""

from __future__ import annotations

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from backend.services.profile_service import get_profile


_driver: webdriver.Chrome | None = None
_current_url: str | None = None
_form_fields: dict = {}
_filled_data: dict = {}
_missing_fields: list[str] = []


def _get_driver() -> webdriver.Chrome:
    global _driver
    if _driver is None:
        options = Options()
        options.add_argument("--start-maximized")
        _driver = webdriver.Chrome(options=options)
    return _driver


def start_autofill(url: str, profile_id: str) -> dict:
    global _current_url, _form_fields, _filled_data, _missing_fields

    profile = get_profile(profile_id)
    if not profile:
        return {"error": "Profile not found", "started": False}

    driver = _get_driver()
    driver.get(url)
    _current_url = url
    time.sleep(2)

    _form_fields = _detect_form_fields(driver)
    _filled_data = {}
    _missing_fields = []

    for field_name, field_info in _form_fields.items():
        value = profile.get(field_name)
        if value:
            try:
                element = driver.find_element(By.CSS_SELECTOR, field_info["selector"])
                element.clear()
                element.send_keys(str(value))
                _filled_data[field_name] = value
            except Exception:
                _missing_fields.append(field_name)
        else:
            _missing_fields.append(field_name)

    return {
        "started": True,
        "url": _current_url,
        "filled": _filled_data,
        "missing": _missing_fields,
        "total_fields": len(_form_fields),
    }


def _detect_form_fields(driver: webdriver.Chrome) -> dict:
    fields = {}
    selectors = {
        "name": ["#name", "#fullname", "#full_name", "input[name='name']", "input[name='fullname']"],
        "email": ["#email", "#e-mail", "input[type='email']", "input[name='email']"],
        "phone": ["#phone", "#mobile", "#telephone", "input[type='tel']", "input[name='phone']"],
        "college": ["#college", "#university", "#institution", "input[name='college']"],
        "usn": ["#usn", "#student_id", "input[name='usn']"],
        "branch": ["#branch", "#department", "select[name='branch']"],
        "degree": ["#degree", "#qualification", "select[name='degree']"],
        "cgpa": ["#cgpa", "#gpa", "#percentage", "input[name='cgpa']"],
        "skills": ["#skills", "textarea[name='skills']"],
    }

    for field_name, selector_list in selectors.items():
        for selector in selector_list:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                fields[field_name] = {
                    "selector": selector,
                    "tag": element.tag_name,
                    "type": element.get_attribute("type") or "",
                }
                break
            except Exception:
                continue

    return fields


def get_form_state() -> dict:
    return {
        "url": _current_url,
        "filled": _filled_data,
        "missing": _missing_fields,
        "total_fields": len(_form_fields),
    }


def close_browser() -> dict:
    global _driver, _current_url, _form_fields, _filled_data, _missing_fields
    if _driver:
        _driver.quit()
        _driver = None
    _current_url = None
    _form_fields = {}
    _filled_data = {}
    _missing_fields = []
    return {"closed": True}
```

- [ ] **Step 4: Add autofill API routes to api.py**

Append to `backend/routes/api.py`:

```python
from backend.services.autofill_service import start_autofill, get_form_state, close_browser


@api_bp.post("/api/autofill/start")
def api_autofill_start() -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    url = data.get("url")
    profile_id = data.get("profile_id")

    if not url or not profile_id:
        return jsonify({"error": "url and profile_id required"}), 400

    result = start_autofill(url, profile_id)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 200


@api_bp.get("/api/autofill/status")
def api_autofill_status() -> tuple[object, int]:
    return jsonify(get_form_state()), 200


@api_bp.post("/api/autofill/close")
def api_autofill_close() -> tuple[object, int]:
    return jsonify(close_browser()), 200
```

- [ ] **Step 5: Test autofill endpoint**

```bash
curl -X POST http://127.0.0.1:5000/api/autofill/start \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/form", "profile_id": "<your_profile_id>"}'
```

Expected: JSON with `started`, `filled`, `missing` fields

- [ ] **Step 6: Commit**

```bash
git add backend/services/autofill_service.py backend/routes/api.py requirements.txt
git commit -m "feat: add browser auto-fill service with Selenium"
```

---

### Task 7: Frontend Integration - Eligibility & Auto-fill

**Files:**
- Modify: `frontend/index.html`

**Interfaces:**
- Consumes: `POST /api/check-eligibility`, `POST /api/autofill/start`, `GET /api/autofill/status`, `POST /api/calendar/create-event`
- Produces: Eligibility display, auto-fill trigger, calendar event creation

- [ ] **Step 1: Add eligibility display section to index.html**

Add after the result-grid section and before the error div:

```html
<div id="eligibility-section" style="display: none; margin-top: 16px; padding: 14px; border-radius: 14px;">
  <h3 id="eligibility-title" style="margin: 0 0 8px;"></h3>
  <div id="eligibility-details"></div>
  <button id="autofill-btn" style="display: none; margin-top: 12px; background: #059669;">Auto-fill Form</button>
  <button id="create-event-btn" style="display: none; margin-top: 12px; margin-left: 8px; background: #4285f4;">Add to Google Calendar</button>
</div>
```

- [ ] **Step 2: Add eligibility check JavaScript**

Add before the closing `</script>` tag:

```javascript
// Eligibility & Auto-fill Integration
const eligibilitySection = document.getElementById('eligibility-section');
const eligibilityTitle = document.getElementById('eligibility-title');
const eligibilityDetails = document.getElementById('eligibility-details');
const autofillBtn = document.getElementById('autofill-btn');
const createEventBtn = document.getElementById('create-event-btn');

let currentSubmissionId = null;
let currentRegistrationLink = null;

async function checkEligibility(submissionId, profileId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/check-eligibility`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ submission_id: submissionId, profile_id: profileId }),
    });

    if (response.ok) {
      const result = await response.json();
      renderEligibility(result);
      return result;
    }
  } catch (e) {
    console.error('Eligibility check failed:', e);
  }
  return null;
}

function renderEligibility(result) {
  eligibilitySection.style.display = 'block';

  if (result.eligible) {
    eligibilitySection.style.background = '#f0fdf4';
    eligibilitySection.style.border = '1px solid #86efac';
    eligibilityTitle.textContent = 'You are eligible!';
    eligibilityTitle.style.color = '#166534';
  } else {
    eligibilitySection.style.background = '#fef2f2';
    eligibilitySection.style.border = '1px solid #fecaca';
    eligibilityTitle.textContent = 'You are not eligible';
    eligibilityTitle.style.color = '#991b1b';
  }

  eligibilityDetails.innerHTML = result.reasons.map(r => `<p style="margin: 4px 0; color: #334155;">${r}</p>`).join('');

  if (result.eligible && currentRegistrationLink) {
    autofillBtn.style.display = 'inline-block';
    createEventBtn.style.display = 'inline-block';
  }
}

autofillBtn.addEventListener('click', async () => {
  if (!currentRegistrationLink || !currentProfileId) {
    alert('Please save your profile first');
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/autofill/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: currentRegistrationLink, profile_id: currentProfileId }),
    });

    if (response.ok) {
      const result = await response.json();
      if (result.missing && result.missing.length > 0) {
        alert(`Form filled! Missing fields: ${result.missing.join(', ')}\nPlease fill them manually.`);
      } else {
        alert('Form filled successfully! Please review and submit manually.');
      }
    }
  } catch (e) {
    alert('Failed to start auto-fill');
  }
});

createEventBtn.addEventListener('click', async () => {
  if (!currentProfileId) {
    alert('Please save your profile first');
    return;
  }

  const eventSummary = `Application Deadline: ${company.textContent} - ${role.textContent}`;
  const eventDescription = `Apply at: ${currentRegistrationLink}\n\nEligibility: ${eligibilityDetails.textContent}`;

  try {
    const response = await fetch(`${API_BASE_URL}/api/calendar/create-event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_id: currentProfileId,
        event_data: {
          summary: eventSummary,
          description: eventDescription,
          start_datetime: new Date(deadline.textContent).toISOString(),
          end_datetime: new Date(new Date(deadline.textContent).getTime() + 3600000).toISOString(),
        },
      }),
    });

    if (response.ok) {
      alert('Event added to Google Calendar!');
    } else {
      alert('Failed to add event. Please connect your Google Calendar first.');
    }
  } catch (e) {
    alert('Failed to create calendar event');
  }
});

// Modify the existing submit button handler to include eligibility check
const originalSubmitHandler = submitButton.onclick;
submitButton.addEventListener('click', async () => {
  // After analysis completes, check eligibility if profile exists
  setTimeout(async () => {
    if (currentProfileId && currentSubmissionId) {
      await checkEligibility(currentSubmissionId, currentProfileId);
    }
  }, 2000);
});
```

- [ ] **Step 3: Test the full flow**

1. Save a profile
2. Submit a job posting PDF/text
3. Verify eligibility check runs automatically
4. Click "Auto-fill Form" if eligible
5. Click "Add to Google Calendar" if connected

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add eligibility display and auto-fill integration"
```

---

## Final Verification

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 2: Manual end-to-end test**

1. Start MongoDB: `mongod`
2. Start Flask: `python -m backend.app`
3. Open `http://127.0.0.1:5000`
4. Create profile
5. Submit job posting
6. Check eligibility
7. Auto-fill form (if eligible)
8. Create calendar event (if connected)

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete FillForm implementation with all features"
```
