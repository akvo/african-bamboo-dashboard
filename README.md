# African Bamboo Dashboard

A full-stack web application with a Next.js frontend, Django REST Framework backend, and PostgreSQL database, orchestrated with Docker Compose.

## Tech Stack

| Layer    | Technology                                            |
| -------- | ----------------------------------------------------- |
| Frontend | Next.js 15 (App Router, Turbopack), React 19, Tailwind CSS 4, Axios |
| Backend  | Django 4.2, Django REST Framework 3.16, SimpleJWT, drf-spectacular |
| Database | PostgreSQL 13 (ltree extension)                       |
| Infra    | Docker Compose                                        |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

## Getting Started

```bash
docker compose up
```

This starts all services:

| Service  | URL                       | Description             |
| -------- | ------------------------- | ----------------------- |
| Frontend | http://localhost:3000     | Next.js application     |
| Backend  | http://localhost:8000     | Django REST API         |
| API Docs | http://localhost:8000/api/docs/ | Swagger UI         |
| PgAdmin  | http://localhost:5050     | Database management UI  |

PgAdmin credentials: `dev@akvo.org` / `password`

## Project Structure

```
├── frontend/          # Next.js 15 application
│   └── src/app/       # App Router pages and layouts
├── backend/           # Django project
│   ├── african_bamboo_dashboard/   # Project settings and root URLs
│   └── api/v1/v1_init/             # API v1 app (views, models, urls)
├── database/
│   ├── docker-entrypoint-initdb.d/ # DB initialization SQL
│   └── script/                     # Utility scripts (e.g., dump-db.sh)
├── docker-compose.yml              # Service definitions
└── docker-compose.override.yml     # Dev overrides (ports, pgadmin)
```

## Development

### Frontend

Commands run inside the `frontend/` directory:

```bash
yarn dev       # Start dev server with Turbopack
yarn build     # Production build
yarn lint      # Run ESLint + Prettier checks
```

### Backend

Commands run inside the `backend/` directory:

```bash
python manage.py migrate                 # Apply database migrations
python manage.py createsuperuser         # Create admin user
python manage.py runserver 0.0.0.0:8000  # Start dev server
```

Code quality:

```bash
black .        # Format Python code
isort .        # Sort imports
flake8         # Lint (max line length: 80)
```

### Database

Dump the database:

```bash
docker compose exec -T db pg_dump --user akvo --clean --create --format plain african_bamboo_dashboard > database/docker-entrypoint-initdb.d/001-init.sql
```

## API

- **Versioning**: URL-path based (`/api/v1/...`)
- **Authentication**: JWT via SimpleJWT (12h access / 7d refresh tokens)
- **Pagination**: LimitOffset (default page size: 10)
- **Schema**: OpenAPI 3.0 auto-generated at `/api/schema/`
- **Documentation**: Interactive Swagger UI at `/api/docs/`

### Authentication (KoboToolbox)

All API requests (except login) require a Bearer token. Obtain one by logging in with your KoboToolbox credentials:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "kobo_url": "https://kf.kobotoolbox.org",
    "kobo_username": "your_username",
    "kobo_password": "your_password"
  }'
```

Response:

```json
{
  "user": { "id": 1, "name": "your_username", "email": "...", ... },
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expiration_time": "2026-02-13T04:07:00Z"
}
```

Use the `token` value as a Bearer token for all subsequent requests:

```
Authorization: Bearer <token>
```

### ODK API — Syncing KoboToolbox Data

The ODK API acts as a local proxy/cache for KoboToolbox. The workflow is:

1. **Register a form** by its KoboToolbox `asset_uid`
2. **Trigger sync** to fetch submissions from KoboToolbox into the local database
3. **Query locally** — list, filter, and retrieve submissions without hitting KoboToolbox again

#### Step 1: Register a Form

Register a KoboToolbox form using its `asset_uid` (found in the KoboToolbox URL or form settings):

```bash
curl -X POST http://localhost:8000/api/v1/odk/forms/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_uid": "aYRqYXmmPLFfbcwC2KAULa",
    "name": "Bamboo Plot Survey"
  }'
```

List all registered forms:

```bash
curl http://localhost:8000/api/v1/odk/forms/ \
  -H "Authorization: Bearer <token>"
```

Get a single form (includes `submission_count`):

```bash
curl http://localhost:8000/api/v1/odk/forms/aYRqYXmmPLFfbcwC2KAULa/ \
  -H "Authorization: Bearer <token>"
```

#### Step 2: Sync Submissions from KoboToolbox

Trigger a sync to pull submissions from KoboToolbox into the local database. The sync uses your stored Kobo credentials and supports incremental sync (only fetches new data since the last sync):

```bash
curl -X POST http://localhost:8000/api/v1/odk/forms/aYRqYXmmPLFfbcwC2KAULa/sync/ \
  -H "Authorization: Bearer <token>"
```

Response:

```json
{
  "synced": 42,
  "created": 42
}
```

- `synced` — total submissions fetched from KoboToolbox
- `created` — new submissions inserted (existing ones are updated)

On subsequent syncs, only submissions newer than the last sync timestamp are fetched.

#### Step 3: Query Submissions Locally

List submissions (paginated, excludes `raw_data` for performance):

```bash
curl http://localhost:8000/api/v1/odk/submissions/ \
  -H "Authorization: Bearer <token>"
```

Filter by form:

```bash
curl "http://localhost:8000/api/v1/odk/submissions/?asset_uid=aYRqYXmmPLFfbcwC2KAULa" \
  -H "Authorization: Bearer <token>"
```

Get full submission detail (includes `raw_data` and `system_data`):

```bash
curl http://localhost:8000/api/v1/odk/submissions/<uuid>/ \
  -H "Authorization: Bearer <token>"
```

Get the latest sync timestamp for a form:

```bash
curl "http://localhost:8000/api/v1/odk/submissions/latest_sync_time/?asset_uid=aYRqYXmmPLFfbcwC2KAULa" \
  -H "Authorization: Bearer <token>"
```

### ODK API — Plots

Plots represent spatial bamboo plot boundaries derived from submissions.

Create a plot:

```bash
curl -X POST http://localhost:8000/api/v1/odk/plots/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "plot_name": "Farmer A",
    "instance_name": "inst-1",
    "polygon_wkt": "POLYGON((38.7 9.0, 38.8 9.0, 38.8 9.1, 38.7 9.1, 38.7 9.0))",
    "min_lat": 9.0, "max_lat": 9.1,
    "min_lon": 38.7, "max_lon": 38.8,
    "form_id": "aYRqYXmmPLFfbcwC2KAULa",
    "region": "Oromia",
    "sub_region": "West Shewa",
    "created_at": 1700000000000
  }'
```

List plots with filters:

```bash
# By form
curl "http://localhost:8000/api/v1/odk/plots/?form_id=aYRqYXmmPLFfbcwC2KAULa" \
  -H "Authorization: Bearer <token>"

# By draft status
curl "http://localhost:8000/api/v1/odk/plots/?is_draft=true" \
  -H "Authorization: Bearer <token>"
```

Find overlapping plots by bounding box:

```bash
curl -X POST http://localhost:8000/api/v1/odk/plots/overlap_candidates/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "min_lat": 9.0, "max_lat": 9.1,
    "min_lon": 38.7, "max_lon": 38.8
  }'
```

### API Endpoint Summary

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/api/v1/auth/login` | Login with KoboToolbox credentials |
| GET | `/api/v1/odk/forms/` | List registered forms |
| POST | `/api/v1/odk/forms/` | Register a new form |
| GET | `/api/v1/odk/forms/{asset_uid}/` | Get form detail |
| DELETE | `/api/v1/odk/forms/{asset_uid}/` | Remove a form |
| POST | `/api/v1/odk/forms/{asset_uid}/sync/` | Sync submissions from KoboToolbox |
| GET | `/api/v1/odk/submissions/` | List submissions (`?asset_uid=` filter) |
| GET | `/api/v1/odk/submissions/{uuid}/` | Get submission detail |
| GET | `/api/v1/odk/submissions/latest_sync_time/` | Latest sync time (`?asset_uid=` required) |
| GET | `/api/v1/odk/plots/` | List plots (`?form_id=`, `?is_draft=` filters) |
| POST | `/api/v1/odk/plots/` | Create a plot |
| GET | `/api/v1/odk/plots/{uuid}/` | Get plot detail |
| PUT | `/api/v1/odk/plots/{uuid}/` | Update a plot |
| DELETE | `/api/v1/odk/plots/{uuid}/` | Delete a plot |
| POST | `/api/v1/odk/plots/overlap_candidates/` | Find overlapping plots |
