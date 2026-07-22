# FillForm Design Specification

## Overview

FillForm is an AI-powered automation system that extracts job posting details, checks user eligibility, sets Google Calendar reminders, and auto-fills registration forms. The system never auto-submits forms—users maintain full control.

## Current State

### Done
- **Backend**: Flask app with `/api/analyze` endpoint
- **Parsing**: PDF and text input handling
- **Extraction**: Regex-based + Groq/Gemini AI extraction (company, role, deadline, CTC, eligibility)
- **Database**: SQLite tables for submissions, profiles, reminders (not integrated)
- **Frontend**: Basic UI to submit text/PDF and display extracted data

### Pending
1. Google Calendar integration for reminders
2. User profile management (API endpoints + UI)
3. Eligibility checking logic (user profile vs job requirements)
4. Form auto-filling (Selenium/Playwright integration)
5. Integration of all components

## Architecture

### Modular Services Approach

```
backend/
├── services/
│   ├── profile_service.py      # CRUD for user profiles (MongoDB)
│   ├── eligibility_service.py  # Check if user matches job requirements
│   ├── calendar_service.py     # Google Calendar OAuth2 + event creation
│   ├── autofill_service.py     # Browser automation (Selenium/Playwright)
│   └── extraction_service.py   # Current Groq/Gemini extraction (existing)
├── routes/
│   └── api.py                  # All API endpoints
├── app.py                      # Flask application
└── config.py                   # Configuration
```

## Database: MongoDB

### User Profile Schema

```javascript
{
  "_id": ObjectId,
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+91-9876543210",
  "college": "ABC Engineering College",
  "usn": "1AB20CS001",
  "branch": "CSE",
  "degree": "B.E.",
  "graduation_year": 2026,
  "tenth_marks": "95%",
  "puc_marks": "92%",
  "semesters": [
    {"sem": 1, "sgpa": 8.5},
    {"sem": 2, "sgpa": 8.8},
    {"sem": 3, "sgpa": 9.0},
    {"sem": 4, "sgpa": 8.9},
    {"sem": 5, "sgpa": 9.1},
    {"sem": 6, "sgpa": 9.2},
    {"sem": 7, "sgpa": 9.3},
    {"sem": 8, "sgpa": 9.4}
  ],
  "yearwise_cgpa": [
    {"year": 1, "cgpa": 8.65},
    {"year": 2, "cgpa": 8.95},
    {"year": 3, "cgpa": 9.15},
    {"year": 4, "cgpa": 9.35}
  ],
  "overall_cgpa": 8.75,
  "backlogs": 0,
  "active_backlogs": 0,
  "interests": ["web development", "AI/ML"],
  "skills": ["Python", "JavaScript", "React", "Node.js"],
  "resume_text": "...",
  "resume_file_path": "/path/to/resume.pdf",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### Calendar Token Storage

```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,  // Reference to profile
  "access_token": "...",
  "refresh_token": "...",
  "token_expiry": ISODate,
  "calendar_id": "primary",
  "created_at": ISODate
}
```

## API Endpoints

### Profile Management
- `POST /api/profile` - Create/Update profile
- `GET /api/profile` - Get current profile
- `PUT /api/profile` - Update profile
- `DELETE /api/profile` - Delete profile

### Eligibility Checking
- `POST /api/check-eligibility` - Takes submission_id, returns eligibility result

### Google Calendar
- `GET /api/calendar/auth` - Redirect to Google OAuth2
- `GET /api/calendar/callback` - Handle OAuth2 callback
- `POST /api/calendar/create-event` - Create calendar event
- `GET /api/calendar/status` - Check if calendar is connected

### Auto-fill
- `POST /api/autofill/start` - Start browser and navigate to form
- `GET /api/autofill/status` - Get current form state
- `POST /api/autofill/fill` - Fill form with profile data
- `POST /api/autofill/submit` - User manually submits (NOT auto-submit)

## Eligibility Checking Logic

```python
def check_eligibility(job_requirements, user_profile):
    result = {
        "eligible": True,
        "reasons": [],
        "warnings": []
    }
    
    # Check batch year
    if job_requirements.batch:
        if user_profile.graduation_year not in job_requirements.batch:
            result.eligible = False
            result.reasons.append(f"Batch mismatch: need {job_requirements.batch}")
    
    # Check branch
    if job_requirements.branches:
        if user_profile.branch not in job_requirements.branches:
            result.eligible = False
            result.reasons.append(f"Branch mismatch: need {job_requirements.branches}")
    
    # Check degree
    if job_requirements.degree:
        if user_profile.degree != job_requirements.degree:
            result.eligible = False
            result.reasons.append(f"Degree mismatch: need {job_requirements.degree}")
    
    # Check percentage/CGPA
    if job_requirements.percentage:
        if user_profile.cgpa < job_requirements.percentage:
            result.eligible = False
            result.reasons.append(f"CGPA below minimum: {user_profile.cgpa} < {job_requirements.percentage}")
    
    # Check backlogs
    if job_requirements.backlog_rule == "no backlog":
        if user_profile.active_backlogs > 0:
            result.eligible = False
            result.reasons.append(f"Active backlogs: {user_profile.active_backlogs}")
    
    return result
```

## Google Calendar Integration

### OAuth2 Flow
1. User authorizes FillForm to access their Google Calendar
2. System stores refresh token in MongoDB
3. When a deadline is detected, system creates calendar event with reminders

### Calendar Event Structure
```python
{
    "summary": "Application Deadline: {company} - {role}",
    "description": f"Apply at: {registration_link}\n\nEligibility: {eligibility_summary}",
    "start": {
        "dateTime": deadline_iso,
        "timeZone": "Asia/Kolkata"
    },
    "end": {
        "dateTime": deadline_iso + 1 hour,
        "timeZone": "Asia/Kolkata"
    },
    "reminders": {
        "useDefault": False,
        "overrides": [
            {"method": "email", "minutes": 7 * 24 * 60},  # 7 days before
            {"method": "popup", "minutes": 24 * 60},       # 1 day before
            {"method": "popup", "minutes": 60}             # 1 hour before
        ]
    }
}
```

## Auto-fill Service

### Flow
1. System extracts registration link from job posting
2. System checks eligibility (must be eligible to proceed)
3. System attempts to open the link in browser
4. System identifies form fields on the page
5. System maps user profile data to form fields
6. System fills available fields, highlights missing fields
7. System shows form to user for review
8. User submits manually (NEVER auto-submit)

### Safety Measures
- Never auto-submit
- Highlight missing fields
- Show preview before submission
- User must click submit button

## Work Split (2 Team Members)

### Skanda: Backend Services
1. **Profile Service** (MongoDB CRUD)
   - Profile schema design
   - API endpoints for profile management
   - Integration with existing submission flow

2. **Eligibility Service**
   - Logic to check user against job requirements
   - API endpoint for eligibility check

3. **Calendar Service**
   - Google Calendar OAuth2 setup
   - Event creation with reminders
   - Token storage in MongoDB

### Manvitha: Frontend + Auto-fill
1. **Frontend: Profile Management UI**
   - Form to enter/edit profile data
   - Display profile summary
   - Integration with backend API

2. **Auto-fill Service**
   - Selenium/Playwright integration
   - Form detection and filling
   - User review and manual submit

3. **Frontend: Integration**
   - Connect all frontend components
   - Handle API calls
   - Display eligibility results

## Integration Points
- Both work on backend services that connect to MongoDB
- Manvitha builds frontend that calls Skanda's APIs
- Auto-fill service uses Profile Service data
