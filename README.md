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
