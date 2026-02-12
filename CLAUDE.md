# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

African Bamboo Dashboard — a full-stack monorepo with a Next.js 15 frontend, Django 4.2 backend (DRF), and PostgreSQL 13 database, all orchestrated via Docker Compose.

## Development Commands

### Starting the environment
```bash
docker-compose up          # Start all services (db, backend, frontend, pgadmin)
docker-compose down        # Stop all services
```

Access points:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger UI: http://localhost:8000/api/docs/
- PgAdmin: http://localhost:5050 (dev@akvo.org / password)

### Frontend (`frontend/`)
```bash
yarn dev        # Dev server with Turbopack (hot reload)
yarn build      # Production build
yarn lint       # ESLint
```

### Backend (`backend/`)
```bash
python manage.py runserver 0.0.0.0:8000
python manage.py migrate
python manage.py test                        # Run all tests
python manage.py test api.v1.v1_init         # Run tests for a specific app
flake8                                       # Lint (max line length: 80)
black .                                      # Format code
isort .                                      # Sort imports
```

## Architecture

### Monorepo Layout
- `frontend/` — Next.js 15 (App Router) with React 19, Tailwind CSS 4, Axios
- `backend/` — Django 4.2 with DRF 3.16, SimpleJWT, drf-spectacular
- `database/` — PostgreSQL init scripts (ltree extension enabled)
- `docker-compose.yml` / `docker-compose.override.yml` — service orchestration

### Frontend
- **Routing**: Next.js App Router (`frontend/src/app/`)
- **Path alias**: `@/*` maps to `./src/*` (configured in `jsconfig.json`)
- **API proxy**: `/api/*` requests are rewritten to `http://backend:8000/api/*` via `next.config.mjs`
- **Styling**: Tailwind CSS 4 via PostCSS

### Backend
- **API versioning**: URL-path versioning (`/api/v1/...`)
- **App structure**: `backend/api/v1/v1_init/` — main v1 API app
- **Settings**: `backend/african_bamboo_dashboard/settings.py`
- **URL root**: `backend/african_bamboo_dashboard/urls.py`
- **Auth**: JWT via SimpleJWT (12h access token, 7d refresh token)
- **Pagination**: LimitOffsetPagination, default page size 10
- **API docs**: Auto-generated OpenAPI 3.0 schema via drf-spectacular

### Data Flow
Frontend (port 3000) → Next.js API rewrite → Backend DRF (port 8000) → PostgreSQL (port 5432)

### Database
- PostgreSQL 13 with ltree extension
- Init script: `database/docker-entrypoint-initdb.d/000-init.sql`
- Credentials: user `akvo`, password `password`, database `african_bamboo_dashboard`

## Code Style

- **Frontend**: ESLint 9 (flat config) + Prettier. Config in `frontend/eslint.config.mjs`
- **Backend**: Black (formatter) + Flake8 (linter, 80 char max) + isort (import sorting). Config in `backend/.flake8`

### Backend Linting Rules (MUST follow when writing Python code)

All backend Python code MUST pass `flake8` with the project config (`backend/.flake8`):
- **Max line length: 80 characters** — no exceptions. Break long strings, imports, and function signatures across multiple lines.
- **No unused imports** (F401) — remove any import that is not used in the file.
- **No unused variables** (F841) — remove or prefix with `_` if intentionally unused.
- Ignored rules: E203 (whitespace before `:`), W503 (line break before binary operator).

When writing backend code, always:
1. Keep every line under 80 characters. Use parentheses, implicit string concatenation, or backslash continuation to break long lines.
2. Run `black . && isort . && flake8` mentally before finalizing code — the CI will fail on any violation.
3. Use double quotes for strings (Black default).
4. Sort imports with isort (stdlib → third-party → local), one import per line for `from` imports when they exceed 80 chars.

### Backend Test Naming Convention

Tests live in `backend/api/v1/<app>/tests/` as a package (with `__init__.py`). Each file tests one endpoint or concern:

- **File naming**: `tests_<resource>_<action>_endpoint.py` — e.g. `tests_login_endpoint.py`, `tests_forms_endpoint.py`, `tests_plots_endpoint.py`
- **Shared helpers**: `mixins.py` — provides a mixin class with auth helpers (e.g. `get_auth_token()`, `get_auth_header()`) that test classes inherit via multiple inheritance
- **Model tests**: `test_models.py` — tests model creation, constraints, and behavior

Examples from the codebase:
```
backend/api/v1/v1_users/tests/
├── __init__.py
├── mixins.py                                  # ProfileTestHelperMixin
├── tests_login_endpoint.py
├── tests_users_me_endpoint.py
├── tests_users_me_update_endpoint.py
├── tests_users_forgot_password_endpoint.py
├── tests_users_reset_password_endpoint.py
└── ...

backend/api/v1/v1_odk/tests/
├── __init__.py
├── mixins.py                                  # OdkTestHelperMixin
├── test_models.py
├── tests_forms_endpoint.py
├── tests_submissions_endpoint.py
└── tests_plots_endpoint.py
```

When creating new tests, always split by endpoint — never put multiple resource tests in one file.
