# FillForm — Auth + Calendar + UI Overhaul

**Date:** 2026-07-22
**Status:** Approved

---

## Overview

Three interconnected features:
1. **Google OAuth Login** — users sign in with Google, profile persists across visits
2. **Add to Calendar** — one-click Google Calendar event creation for active deadlines
3. **UI Cleanup** — reorganize layout, remove debug artifacts, improve visual hierarchy

---

## 1. Google OAuth Login

### Backend

**New file: `backend/services/auth_service.py`**

- Uses Google OAuth2 web flow (same library as calendar: `google-auth-oauthlib`)
- Scopes: `openid email profile` (minimal — just for identity)
- Stores users in `users` MongoDB collection:
  ```
  {
    google_id: str,
    email: str,
    name: str,
    picture: str,
    profile_id: str | null,   // links to profiles collection
    created_at: str,
    updated_at: str
  }
  ```
- Session via `flask.session` (signed cookie, requires `SECRET_KEY`)

**New routes in `backend/routes/api.py`:**

| Route | Method | Description |
|-------|--------|-------------|
| `/api/auth/login` | GET | Returns Google OAuth authorization URL |
| `/api/auth/callback` | GET | Handles OAuth redirect, creates/finds user, sets session |
| `/api/auth/me` | GET | Returns current user + linked profile from session (401 if not logged in) |
| `/api/auth/logout` | POST | Clears session cookie |

**New env vars:**
- `GOOGLE_LOGIN_CLIENT_ID` — separate from calendar client ID (or reuse if same project)
- `GOOGLE_LOGIN_CLIENT_SECRET`
- `SECRET_KEY` — Flask session signing key (random string)

**Flow:**
1. Frontend calls `GET /api/auth/login` → gets `auth_url`
2. User redirected to Google → consents → redirected to `/api/auth/callback`
3. Callback: exchange code for tokens, get user info, upsert into `users` collection, set `session["user_id"]`
4. Redirect back to frontend with session cookie set

### Frontend

- **Login screen:** centered card with Google logo + "Sign in with Google" button
- **Post-login check:** `GET /api/auth/me`
  - If `profile_id` is null → show profile creation form
  - If `profile_id` exists → load profile, show main app
- **Profile form fields:** name, email (pre-filled from Google), phone, degree, branch, batch, percentage, backlogs
- **Nav bar:** shows user name/avatar + logout button
- **Logout:** `POST /api/auth/logout` → clear state → show login screen

### Session Persistence
- Cookie expires after 7 days
- `flask.session` is signed but not encrypted (no sensitive data stored — just `user_id`)
- On each page load, frontend calls `/api/auth/me` to validate session

---

## 2. Add to Calendar Button

### Prerequisites
- Google OAuth for calendar already exists in `calendar_service.py`
- Requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in env (may share with login or separate)
- User must have connected their calendar (one-time OAuth grant)

### Frontend Flow
1. After analysis, if deadline status is `active` or `today`:
   - Call `GET /api/calendar/status?profile_id={id}`
   - If `connected: true` → show "Add to Calendar" button on deadline card
   - If `connected: false` → show "Connect Google Calendar" link that triggers calendar OAuth
2. On "Add to Calendar" click:
   - Build event data from analysis results:
     - `summary`: `{company} — {role}` (or "FillForm Reminder" if missing)
     - `start_datetime`: deadline time
     - `end_datetime`: deadline time + 1 hour
     - `description`: registration link, CTC, eligibility info
   - Call `POST /api/calendar/create-event` with `{ profile_id, event_data }`
   - Show success toast: "Event created in Google Calendar"
   - Disable button, change text to "Added ✓"
3. If calendar not connected, clicking "Connect Google Calendar":
   - Call `GET /api/calendar/auth?profile_id={id}` → get `auth_url`
   - Open in new tab/popup
   - After callback, re-check status and show button

### Button Placement
- Appears inside the deadline result card, below the status pill
- Only visible when deadline is `active` or `today`
- Styled as a secondary action (outlined button) next to the status indicator

---

## 3. UI Cleanup

### Layout Changes

**Remove:**
- The `<pre id="output">` debug panel (hide or remove entirely)
- The duplicate `showPageWarning()` function (defined twice)

**Restructure results into sections:**

```
┌─────────────────────────────────────────────┐
│  NAV BAR: FillForm    [User Name] [Logout]  │
├─────────────────────────────────────────────┤
│                                             │
│  HERO: Title + Description                  │
│                                             │
├──────────────────────┬──────────────────────┤
│  INPUT SECTION       │  FILE UPLOAD         │
│  [textarea]          │  [file input]        │
│                      │  [Analyze button]    │
├──────────────────────┴──────────────────────┤
│                                             │
│  JOB OVERVIEW CARD                          │
│  ┌─────────┬─────────┬─────────┐           │
│  │Company  │Role     │CTC      │           │
│  ├─────────┼─────────┼─────────┤           │
│  │Eligibility         │Criteria │           │
│  └─────────┴─────────┴─────────┘           │
│                                             │
│  DEADLINE & ACTIONS CARD                    │
│  ┌─────────────────────────────────┐       │
│  │ Deadline: Jul 25, 2026          │       │
│  │ [Active] ████████░░ 2d 5h left  │       │
│  │ [Add to Calendar]               │       │
│  │ [Quick Apply →]                 │       │
│  └─────────────────────────────────┘       │
│                                             │
│  JOB SUMMARY CARD                           │
│  Overview | Highlights | Responsibilities   │
│  Requirements | Benefits                    │
│                                             │
└─────────────────────────────────────────────┘
```

### Style Changes
- Cards get subtle hover: `box-shadow` lift on hover
- Consistent spacing: `24px` between sections, `16px` between cards within sections
- Better typography: `h1` 28px, card labels 12px uppercase, values 16-18px
- Mobile: stack cards vertically, full-width input
- Loading state: spinner overlay on the input section during analysis
- Toast notifications for calendar actions (bottom-right, auto-dismiss)

### Component Breakdown (within single HTML file)
- `renderNav(user)` — nav bar with user info
- `renderLoginForm()` — Google sign-in button
- `renderProfileForm()` — first-time profile creation
- `renderApp(profile)` — main application view
- `renderResults(extracted)` — reorganized result cards
- `renderDeadlineCard(deadline, status)` — deadline card with calendar button
- `showToast(message, type)` — notification toasts

---

## Data Flow Summary

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────▶│  Flask   │────▶│ MongoDB  │
│ (HTML)   │◀────│  Backend │◀────│          │
└──────────┘     └──────────┘     └──────────┘
                       │
                       ▼
                 ┌──────────┐
                 │  Google  │
                 │  OAuth2  │
                 └──────────┘
```

**Collections:**
- `users` — google_id, email, name, picture, profile_id
- `profiles` — existing, linked from users
- `calendar_tokens` — existing, linked from profiles
- `submissions` — existing, for analysis history

---

## Environment Variables

```env
# Existing
GROQ_API_KEY=...
MONGO_URI=mongodb://localhost:27017

# New / Required
SECRET_KEY=<random-secret-for-flask-sessions>
GOOGLE_LOGIN_CLIENT_ID=<from Google Cloud Console>
GOOGLE_LOGIN_CLIENT_SECRET=<from Google Cloud Console>

# Existing (for calendar — may share with login or separate)
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/services/auth_service.py` | **Create** | Google OAuth login, session mgmt, user CRUD |
| `backend/routes/api.py` | **Modify** | Add auth routes, calendar status route already exists |
| `backend/app.py` | **Modify** | Add `SECRET_KEY` config, session config |
| `backend/.env` | **Modify** | Add new env vars |
| `frontend/index.html` | **Modify** | Full UI overhaul, login flow, calendar button, remove debug |
