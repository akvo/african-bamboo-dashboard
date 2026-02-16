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
│   ├── utils/                      # Shared utilities (kobo_client, polygon, encryption)
│   └── api/v1/
│       ├── v1_init/               # Health-check / init endpoints
│       ├── v1_users/              # Auth & user management (JWT, Kobo login)
│       └── v1_odk/                # ODK data (forms, submissions, plots)
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

Run tests:

```bash
docker compose exec backend ./test.sh   # Full test suite with coverage
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

Use the returned `token` as a Bearer token:

```
Authorization: Bearer <token>
```

### ODK API — Forms & Sync

The ODK API acts as a local proxy/cache for KoboToolbox:

1. **Register a form** by its KoboToolbox `asset_uid`
2. **Configure field mappings** to map form fields to plot attributes
3. **Trigger sync** to fetch submissions and auto-generate plots
4. **Query locally** — list, filter, and approve/reject submissions

#### Register a Form

```bash
curl -X POST http://localhost:8000/api/v1/odk/forms/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "asset_uid": "aYRqYXmmPLFfbcwC2KAULa", "name": "Bamboo Plot Survey" }'
```

#### Configure Field Mappings

Fetch available fields from KoboToolbox:

```bash
curl http://localhost:8000/api/v1/odk/forms/aYRqYXmmPLFfbcwC2KAULa/form_fields/ \
  -H "Authorization: Bearer <token>"
```

Save mappings (comma-separated for multi-value fields):

```bash
curl -X PATCH http://localhost:8000/api/v1/odk/forms/aYRqYXmmPLFfbcwC2KAULa/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "polygon_field": "consent_group/consented/boundary_mapping/Open_Area_GeoMapping",
    "region_field": "region",
    "sub_region_field": "woreda",
    "plot_name_field": "consent_group/consented/First_Name,consent_group/consented/Father_s_Name"
  }'
```

#### Sync Submissions

```bash
curl -X POST http://localhost:8000/api/v1/odk/forms/aYRqYXmmPLFfbcwC2KAULa/sync/ \
  -H "Authorization: Bearer <token>"
```

Response:

```json
{
  "synced": 42,
  "created": 42,
  "plots_created": 42,
  "plots_updated": 0
}
```

Sync automatically creates/updates a Plot for each Submission using the configured field mappings.

### ODK API — Submissions & Approval

List submissions:

```bash
curl "http://localhost:8000/api/v1/odk/submissions/?asset_uid=aYRqYXmmPLFfbcwC2KAULa" \
  -H "Authorization: Bearer <token>"
```

Approve or reject a submission:

```bash
# Approve (approval_status: 1)
curl -X PATCH http://localhost:8000/api/v1/odk/submissions/<uuid>/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "approval_status": 1, "reviewer_notes": "Boundary verified" }'

# Reject (approval_status: 2)
curl -X PATCH http://localhost:8000/api/v1/odk/submissions/<uuid>/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "approval_status": 2, "reviewer_notes": "Polygon too small" }'
```

Approval status: `null` = Pending, `1` = Approved, `2` = Rejected.

### ODK API — Plots

Plots are auto-generated during sync. They cannot be created manually (POST returns 405).

List plots with filters:

```bash
# By form
curl "http://localhost:8000/api/v1/odk/plots/?form_id=aYRqYXmmPLFfbcwC2KAULa" \
  -H "Authorization: Bearer <token>"

# By approval status
curl "http://localhost:8000/api/v1/odk/plots/?status=pending" \
  -H "Authorization: Bearer <token>"
```

Update plot geometry:

```bash
curl -X PATCH http://localhost:8000/api/v1/odk/plots/<uuid>/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "polygon_wkt": "POLYGON((38.7 9.0, 38.8 9.0, 38.8 9.1, 38.7 9.1, 38.7 9.0))",
    "min_lat": 9.0, "max_lat": 9.1, "min_lon": 38.7, "max_lon": 38.8
  }'
```

Find overlapping plots by bounding box:

```bash
curl -X POST http://localhost:8000/api/v1/odk/plots/overlap_candidates/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{ "min_lat": 9.0, "max_lat": 9.1, "min_lon": 38.7, "max_lon": 38.8 }'
```

### API Endpoint Summary

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/api/v1/auth/login` | Login with KoboToolbox credentials |
| GET | `/api/v1/odk/forms/` | List registered forms |
| POST | `/api/v1/odk/forms/` | Register a new form |
| GET | `/api/v1/odk/forms/{asset_uid}/` | Get form detail |
| PATCH | `/api/v1/odk/forms/{asset_uid}/` | Update form (field mappings) |
| DELETE | `/api/v1/odk/forms/{asset_uid}/` | Remove a form |
| GET | `/api/v1/odk/forms/{asset_uid}/form_fields/` | List available KoboToolbox fields |
| POST | `/api/v1/odk/forms/{asset_uid}/sync/` | Sync submissions from KoboToolbox |
| GET | `/api/v1/odk/submissions/` | List submissions (`?asset_uid=` filter) |
| GET | `/api/v1/odk/submissions/{uuid}/` | Get submission detail |
| PATCH | `/api/v1/odk/submissions/{uuid}/` | Update approval status and notes |
| GET | `/api/v1/odk/submissions/latest_sync_time/` | Latest sync time (`?asset_uid=` required) |
| GET | `/api/v1/odk/plots/` | List plots (`?form_id=`, `?status=` filters) |
| GET | `/api/v1/odk/plots/{uuid}/` | Get plot detail |
| PATCH | `/api/v1/odk/plots/{uuid}/` | Update plot (geometry) |
| DELETE | `/api/v1/odk/plots/{uuid}/` | Delete a plot |
| POST | `/api/v1/odk/plots/overlap_candidates/` | Find overlapping plots |
