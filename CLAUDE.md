# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kronos Backend is a Django 5.0.6 + GraphQL API service for the Kronos algorithmic trading platform (XAUUSD/Gold, ICT/SMC strategy). It is one microservice in a larger Docker Compose stack — see the parent `CLAUDE.md` for the full system architecture.

## Commands

```bash
# Run the development server
python manage.py runserver

# Apply migrations
python manage.py migrate

# Create a new migration
python manage.py makemigrations

# Django shell
python manage.py shell

# Run tests
python manage.py test

# Run a single test module
python manage.py test api.tests

# Collect static files
python manage.py collectstatic --no-input

# Start Celery worker
celery -A Kronos_Backend worker --loglevel=info

# Start Celery beat scheduler
celery -A Kronos_Backend beat --loglevel=info

# Build Docker image
docker build -t kronos-backend .
```

## Environment Variables

The app reads from a `.env` file via `python-dotenv`. Required keys:
- `SECRET_KEY` — Django secret key
- `NAME`, `USER`, `PASSWORD`, `HOST`, `PORT` — PostgreSQL connection

## Architecture

### App Name
The Django app directory is `apis/` (registered as `"apis"` in `INSTALLED_APPS`). All imports use `apis.*`.

### GraphQL Schema
The entire API surface is GraphQL at `/graphql/`. There are no REST views (`api/views.py` is empty).

- **Schema root**: `api/schema/__init__.py` — assembles `Query` and `Mutation` from sub-modules
- **Query auto-discovery**: `api/schema/query/__init__.py` dynamically imports every `.py` file in its directory via `importlib` and merges them into `CustomQuery` using multiple inheritance. Adding a new query file means creating a class whose name is the CamelCase of the filename.
- **Mutations** are organized by role in `api/schema/mutation/`:
  - `admin/` — strategy CRUD, risk profiles (requires admin auth)
  - `broker/` — broker registration
  - `user/` — login, strategy subscription, position management, backtesting

### Authentication
JWT-based via `django-graphql-jwt`. Token is passed in the `Authorization: JWT <token>` header. Auth decorators live in `api/schema/utils/auth.py` (`@user_authenticate`, `@admin_authenticate`).

JWT expiry: 6 hours. No refresh tokens by default.

### Data Models (`api/models.py`)
All models inherit from `BaseModel` (UUID primary key, `created_at`, `modified_at`). Key models:
- `User` — custom auth user (email as `USERNAME_FIELD`)
- `Strategy` → `UserStrategy` → `Position` → `Order` / `Trigger`
- `CurrencyPair`, `Signal`, `UserBroker`, `Action`

There is a parallel **SQLAlchemy** model layer in `utils/models.py` that mirrors the Django ORM models. It connects directly to `postgresql://postgres:kronos123@127.0.0.1:5432/Kronos`. Django migrations do not manage these; they exist for use by non-Django services in the stack.

### Celery
Async task queue using Redis as broker (`redis://redis:6379`). Results stored in Django DB (`CELERY_RESULT_BACKEND = 'django-db'`). Beat scheduler uses `DatabaseScheduler` (schedules stored in DB, managed via Django admin).

### Encryption Utilities
`Kronos_Backend/utils/encrypt_decrypt.py` and `decrypt_env.py` handle field-level encryption for sensitive broker credentials stored in the DB.

## GraphQL Endpoint

The GraphQL endpoint is mounted at the root via `apis.urls` (included from `Kronos_Backend/urls.py`). Check `api/urls.py` for the exact path (typically `/graphql/`).
