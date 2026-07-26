# FillForm

An AI-powered form automation tool that extracts information from documents, checks eligibility, manages deadlines, and auto-fills applications — so you don't have to.

---

## Features

- **Document Parsing** — Upload PDFs or paste text/links; FillForm extracts structured data automatically
- **AI-Powered Analysis** — Groq LLM extracts deadlines, requirements, and key fields from job/internship postings
- **Eligibility Checking** — Cross-references your profile against posting requirements (branch, degree, CGPA, backlogs)
- **Google Calendar Integration** — One-click deadline events with OAuth-based calendar sync
- **Profile Management** — Store your academic and personal details for repeated use
- **Google OAuth Login** — Secure sign-in with PKCE flow

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask (Python 3.13) |
| Frontend | Vanilla HTML/CSS/JS (single-page app) |
| Databases | MongoDB (profiles) + SQLite (submissions) |
| AI | Groq LLM (`llama-3.3-70b-versatile`) |
| Auth | Google OAuth 2.0 with PKCE |
| Calendar | Google Calendar API |
| Linting | Ruff |
| Testing | pytest + mongomock |
| CI | GitHub Actions |

---

## Prerequisites

- Python 3.13+
- MongoDB (local or Atlas)
- A [Groq API key](https://console.groq.com/) (for AI analysis)
- Google Cloud project with OAuth 2.0 credentials (for login + calendar)

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Skanda02/FillForm.git
cd FillForm
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
cp .env.example backend/.env
```

Edit both `.env` files with your actual keys — see [Environment Variables](#environment-variables) for details.

### 5. Start MongoDB

```bash
# If using local MongoDB:
mongod

# If using MongoDB Atlas, just set MONGO_URI in .env to your connection string
```

### 6. Run the application

```bash
python -m backend.app
```

The server starts at **http://localhost:5000**. Open this URL in your browser to access the app.

---

## Environment Variables

### Root `.env`

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (Calendar API) | `your-client-id.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret (Calendar API) | `your-client-secret` |

### `backend/.env`

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key for LLM analysis | `gsk_...` |
| `SECRET_KEY` | Flask session secret key | any random string |
| `GOOGLE_LOGIN_CLIENT_ID` | Google OAuth client ID (user login) | `your-client-id.apps.googleusercontent.com` |
| `GOOGLE_LOGIN_CLIENT_SECRET` | Google OAuth client secret (user login) | `your-client-secret` |

---

## Project Structure

```
FillForm/
├── backend/
│   ├── app.py                  # Flask application entry point
│   ├── config.py               # Configuration and env var helpers
│   ├── database.py             # MongoDB connection
│   ├── routes/
│   │   └── api.py              # All API route definitions
│   └── services/
│       ├── analyzer.py         # Local text analysis (fallback)
│       ├── auth_service.py     # Google OAuth login (PKCE)
│       ├── autofill.py         # Auto-fill profile builder
│       ├── calendar_service.py # Google Calendar integration
│       ├── eligibility_service.py # Eligibility checker
│       ├── groq_service.py     # Groq LLM extraction
│       ├── parser.py           # PDF/text/URL input parsing
│       ├── profile_service.py  # Profile CRUD operations
│       └── reminders.py        # Reminder plan builder
├── database/
│   └── models.py               # SQLite schema and queries
├── frontend/
│   └── index.html              # Single-page frontend app
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── test_api.py             # API endpoint tests
│   ├── test_eligibility.py     # Eligibility logic tests
│   └── test_profile.py         # Profile service tests
├── .github/workflows/
│   └── ci.yml                  # GitHub Actions CI pipeline
├── .env.example                # Environment variable template
├── requirements.txt            # All dependencies
├── ruff.toml                   # Linter configuration
└── README.md
```

---

## API Reference

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/login` | Get Google OAuth login URL |
| GET | `/api/auth/callback` | OAuth callback handler |
| GET | `/api/auth/me` | Get current authenticated user |
| POST | `/api/auth/logout` | Log out (clear session) |

### Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profiles` | List all profiles |
| GET | `/api/profiles/default` | Get most recent profile |
| GET | `/api/profiles/<id>` | Get a specific profile |
| POST | `/api/profiles` | Create a new profile |
| PUT | `/api/profiles/<id>` | Update a profile |
| DELETE | `/api/profiles/<id>` | Delete a profile |
| POST | `/api/auth/profile` | Create profile for logged-in user |

### Analysis & Eligibility

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Analyze text/PDF/link with AI |
| POST | `/api/check-eligibility` | Check profile eligibility against a submission |
| GET | `/api/diag` | Diagnostic endpoint (Groq key status) |

### Calendar

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/calendar/auth` | Get Google Calendar OAuth URL |
| GET | `/api/calendar/callback` | Calendar OAuth callback |
| POST | `/api/calendar/create-event` | Create a calendar event |
| GET | `/api/calendar/status` | Check calendar connection status |

---

## Development

All dependencies (including dev/test) are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Linting

```bash
ruff check .                # Check for lint errors
ruff format --check .       # Check formatting
ruff format .               # Auto-format
```

### Running Tests

```bash
pytest tests/ -v            # Run all tests
pytest tests/test_api.py -v # Run API tests only
```

Tests use `mongomock` — no running MongoDB instance needed for the test suite.

### CI Pipeline

GitHub Actions runs on every push/PR to `main`:

1. **Lint** — `ruff check` + `ruff format --check`
2. **Test** — `pytest` with a MongoDB service container

---

## How It Works

1. **Sign in** with your Google account
2. **Create a profile** with your academic details (degree, branch, CGPA, etc.)
3. **Paste a job/internship posting** or upload a PDF
4. AI **extracts key information** — deadlines, eligibility criteria, requirements
5. FillForm **checks your eligibility** against the posting
6. **Add deadlines to Google Calendar** with one click
