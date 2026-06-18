# Students Connect — Authentication Module

## Overview

This is the Authentication module for the **Students Connect** backend API. It implements
a 3-step registration flow, JWT-based sessions, email OTP verification, and password
management — all following Clean Architecture with FastAPI + PostgreSQL.

---

## Tech Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| Framework    | FastAPI                           |
| Database     | PostgreSQL 16 + asyncpg           |
| ORM          | SQLAlchemy 2.x (async)            |
| Migrations   | Alembic                           |
| Validation   | Pydantic v2                       |
| Auth         | JWT (python-jose) + bcrypt        |
| Email        | aiosmtplib (async SMTP)           |
| Containers   | Docker + Docker Compose           |
| Testing      | pytest + pytest-asyncio + httpx   |

---

## Project Structure

```
students_connect/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py          ← API router aggregator
│   │       └── routes/
│   │           └── auth.py          ← 10 auth endpoints
│   ├── core/
│   │   ├── config.py                ← Settings (pydantic-settings)
│   │   ├── dependencies.py          ← FastAPI auth dependencies
│   │   ├── exceptions.py            ← Custom HTTP exceptions
│   │   └── security.py             ← JWT + bcrypt utilities
│   ├── db/
│   │   ├── base.py                  ← DeclarativeBase + model imports
│   │   └── session.py              ← Async engine + session factory
│   ├── models/
│   │   ├── otp.py                   ← OTP table
│   │   └── user.py                  ← Users table
│   ├── repositories/
│   │   ├── otp_repository.py        ← OTP DB queries
│   │   └── user_repository.py       ← User DB queries
│   ├── schemas/
│   │   └── auth.py                  ← Pydantic request/response schemas
│   ├── services/
│   │   └── auth_service.py          ← All auth business logic
│   ├── utils/
│   │   ├── email.py                 ← Async email sender
│   │   └── otp.py                   ← Secure OTP generator
│   └── main.py                      ← App factory + global error handlers
├── alembic/
│   ├── env.py                       ← Async Alembic config
│   └── versions/
│       └── 001_auth.py              ← Migration: users + otps tables
├── tests/
│   ├── conftest.py                  ← Shared fixtures (in-memory DB + client)
│   └── auth/
│       ├── test_auth_routes.py      ← Integration tests (HTTP routes)
│       ├── test_auth_service.py     ← Unit tests (service layer)
│       └── test_security.py        ← Unit tests (JWT + hashing)
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

---

## Registration Flow

```
POST /signup          → Creates user, sends email OTP
POST /verify-otp      → Validates OTP, marks it used
POST /create-password → Sets password, returns JWT tokens
```

---

## API Endpoints

| Method | Endpoint                       | Auth Required | Description                    |
|--------|--------------------------------|---------------|--------------------------------|
| POST   | `/api/v1/auth/signup`          | No            | Register — sends OTP           |
| POST   | `/api/v1/auth/verify-otp`      | No            | Verify email OTP               |
| POST   | `/api/v1/auth/create-password` | No            | Set password, get tokens       |
| POST   | `/api/v1/auth/login`           | No            | Login with email/phone         |
| POST   | `/api/v1/auth/refresh`         | No            | Refresh access token           |
| POST   | `/api/v1/auth/logout`          | Bearer JWT    | Logout                         |
| POST   | `/api/v1/auth/forgot-password` | No            | Request password reset OTP     |
| POST   | `/api/v1/auth/verify-reset-otp`| No            | Verify password reset OTP      |
| POST   | `/api/v1/auth/reset-password`  | No            | Reset password with OTP        |
| PUT    | `/api/v1/auth/change-password` | Bearer JWT    | Change password (logged in)    |

---

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env — fill in SMTP credentials and change secret keys
```

### 2. Start with Docker Compose

```bash
docker compose up --build
```

Services started:
- **App** → http://localhost:8000
- **Swagger UI** → http://localhost:8000/docs
- **pgAdmin** → http://localhost:5050 (admin@admin.com / admin)

### 3. Run database migrations

```bash
docker compose exec app alembic upgrade head
```

### 4. Health check

```bash
curl http://localhost:8000/health
# {"status": "ok", "app": "StudentsConnect"}
```

---

## Running Without Docker

```bash
# Create virtualenv
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set env vars
cp .env.example .env
# Edit DATABASE_URL to point at your local Postgres

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

---

## Running Tests

Tests use an **in-memory SQLite** database — no Postgres or Docker required.

```bash
# Install deps
pip install -r requirements.txt
pip install aiosqlite          # SQLite async driver for tests

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/auth/test_security.py -v
pytest tests/auth/test_auth_service.py -v
pytest tests/auth/test_auth_routes.py -v
```

---

## Environment Variables

| Variable                    | Required | Description                           |
|-----------------------------|----------|---------------------------------------|
| `SECRET_KEY`                | Yes      | App secret key                        |
| `DATABASE_URL`              | Yes      | PostgreSQL async URL (asyncpg)        |
| `JWT_SECRET_KEY`            | Yes      | JWT signing key                       |
| `JWT_ALGORITHM`             | No       | Default: `HS256`                      |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| No      | Default: `30`                         |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No       | Default: `7`                          |
| `SMTP_HOST`                 | Yes      | SMTP server host                      |
| `SMTP_PORT`                 | No       | Default: `587`                        |
| `SMTP_USERNAME`             | Yes      | SMTP username                         |
| `SMTP_PASSWORD`             | Yes      | SMTP password / app password          |
| `EMAIL_FROM`                | Yes      | Sender email address                  |
| `OTP_EXPIRE_MINUTES`        | No       | Default: `10`                         |

---

## Security Notes

- Passwords hashed with **bcrypt** (cost factor 12).
- JWTs use **HS256** with separate signing key from app secret.
- Access tokens expire in **30 minutes**; refresh tokens in **7 days**.
- OTPs are **6-digit, cryptographically random**, expire in **10 minutes**, and are
  single-use (marked used immediately on verification).
- Previous OTPs for the same email+purpose are invalidated when a new one is issued.
- `forgot-password` always returns HTTP 200 regardless of whether the email exists,
  preventing **email enumeration**.
- Passwords must contain uppercase, lowercase, digit, and special character.

---

## Next Module

Once this module is approved, the next step is the **Profile module**.
Wait for instruction before proceeding.
