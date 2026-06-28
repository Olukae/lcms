# LCMS — Learning Curriculum Management System

A Flask-based curriculum proposal and approval system built for Lagos State
University (LASU), modeling NUC's multi-stage accreditation workflow:

```
Draft → Departmental Review (HOD) → Faculty Board (Dean) → Quality Assurance
→ Senate Ratification (Admin) → Approved
```

Returns at any review stage send the proposal back to the originating
lecturer with comments; resubmission re-enters at Departmental Review.

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # edit SECRET_KEY / JWT_SECRET_KEY for real use
python seed.py                    # creates tables + one demo account per role
python run.py                     # http://127.0.0.1:5000
```

Demo accounts (password `Password123!` for all):

| Role | Email |
|---|---|
| Lecturer | lecturer@lasu.edu.ng |
| HOD | hod@lasu.edu.ng |
| Dean | dean@lasu.edu.ng |
| QA Officer | qa@lasu.edu.ng |
| Admin (also acts as Senate liaison — see below) | admin@lasu.edu.ng |

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

22 tests cover the full approval pipeline, RBAC scope enforcement
(department/faculty boundaries), return-and-resubmit, version numbering,
autosave isolation, and the password reset flow.

## Architecture

- **Models** (`app/models/`) — `User`, `Faculty`/`Department`/`Programme`/`Course`,
  `Curriculum`/`CurriculumVersion`, `WorkflowStage`/`ApprovalAction`, `AuditLog`/`Notification`.
- **Services** (`app/services/`) — all business logic lives here, not in routes:
  - `workflow_service.py` — the state machine. `STAGE_RULES` is the single
    source of truth for stage→role mapping and sequencing; routes never
    hardcode the chain.
  - `version_control_service.py` — append-only snapshotting with a generated
    plain-English diff (`change_summary`) on every workflow transition.
  - `audit_service.py` — append-only audit log writer, called from every
    state-changing action.
  - `notification_service.py` — in-app notifications; email is opt-in and
    degrades gracefully if SMTP isn't configured.
  - `pdf_service.py` / `report_service.py` — PDF export and aggregate reporting.
- **Auth** — JWT stored in an HttpOnly cookie (`flask-jwt-extended`), with
  CSRF double-submit protection on state-changing requests. `app/auth/decorators.py`
  has `@login_required` and `@role_required(...)` — role checks only, scope
  checks (department/faculty) happen inside each route/service.
- **Blueprints** — one per concern: `auth`, `curriculum`, five `dashboards/*`
  (one per role), `reports`, and `views` (page routes).
- **Frontend** — server-rendered Jinja2 + vanilla JS/fetch, no build step.
  Navy/gold institutional design system in `app/static/css/lcms.css`.

## Resolved ambiguity: Senate as a role

The spec defines five system actors (Lecturer, HOD, Dean, QA Officer, Admin)
but a four-stage approval chain ending in Senate. Senate sittings are
modeled as offline/in-person; there's no online "Senate user." The System
Administrator account doubles as the Senate/Registry liaison and records
the sitting's outcome via `/dashboard/admin/senate/<id>/ratify`.

This is implemented as a single entry in `STAGE_RULES` inside
`workflow_service.py` (`STATUS_SENATE_REVIEW` → `role_required: ROLE_ADMIN`).
If Senate needs to become a first-class role later (e.g. a Registrar account
that can ratify without full admin rights), that's the only line to change —
add `role='senate'` to the `User` model, point this rule at it, and give
that role a stripped-down dashboard.

## Database

Defaults to SQLite for local development (zero setup). For production,
set `DATABASE_URL` to a MySQL connection string in `.env` — `ProdConfig` in
`app/config.py` already points at MySQL via `PyMySQL`. `Flask-Migrate` is
wired up for schema migrations (`flask db init / migrate / upgrade`).

## Known non-blocking items

- SQLAlchemy and `datetime.utcnow()` deprecation warnings appear under
  pytest (SQLAlchemy 2.0 / Python 3.12 forward-compat notices). They don't
  affect correctness — left as-is rather than churning the codebase on a
  cosmetic fix, but worth migrating to `Session.get()` / timezone-aware
  datetimes before this goes to production.
- Email delivery is optional (`MAIL_SUPPRESS_SEND`); if SMTP isn't
  configured, password reset returns the token directly in the API
  response instead of emailing it, so the flow stays usable in dev/demo
  environments. Configure `MAIL_*` in `.env` for production.
