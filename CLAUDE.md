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
