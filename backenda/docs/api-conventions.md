# ADC API Conventions & Error Formats

This document defines the architectural conventions, error response formats, authentication mechanics, and data standards used across the **ADC (Autonomous Distributed AI Trainer)** backend API.

---

## 1. Base URL & Routing Structure

- **Current Version:** `/api/v1`
- **Health Endpoints:**
  - `GET /health` — Liveness probe (process up)
  - `GET /health/ready` — Readiness probe (database connection active)
- **Interactive Documentation:**
  - Swagger UI: `http://localhost:8000/docs` (development only)
  - ReDoc: `http://localhost:8000/redoc` (development only)

### Route Groups
| Group | Path Prefix | Description |
|-------|-------------|-------------|
| Authentication & Accounts | `/api/v1/auth` | Registration, login, logout, profile, session revocation |
| Machine Identity & Pairing | `/api/v1/machines` | Agent registration, pairing challenges, heartbeats, role switches |
| Projects | `/api/v1/projects` | Distributed training projects, lifecycle, state transitions |
| Datasets & Packages | `/api/v1/projects/{id}/...` | Training code packages, manifests, dataset uploads |
| Resources | `/api/v1/resources` | Worker hardware detection, allocation budgets, contribution pause |
| Training & Checkpoints | `/api/v1/projects/{id}/training` | PyTorch training execution, telemetry metrics, model checkpoints |
| Agent Tasks | `/api/v1/agent/tasks` | Worker job dispatch, task lease acquisition, step reporting |

---

## 2. Authentication & Session Architecture

ADC separates **User Identity** from **Machine Identity**:

1. **User Authentication:**
   - Supported via `Authorization: Bearer <token>` header AND HTTP-only cookies (`access_token`, `refresh_token`).
   - Token algorithm: `HS256` signed JWTs with expiration (`exp`), issued-at (`iat`), and subject (`sub` user UUID).
   - Sessions are tracked in the `user_sessions` database table, allowing remote device revocation.

2. **Machine Authentication:**
   - Cryptographic Ed25519 key-pair identity generated locally on machine setup.
   - Verified via challenge-response during agent connection.
   - Enforces "One Machine, One Role" (Master OR Worker).

3. **CSRF Protection:**
   - Implements the Double-Submit Cookie pattern.
   - Requests authenticated via cookies must include the `X-CSRF-Token` header matching the `csrftoken` cookie.
   - Requests using `Authorization: Bearer` headers are immune to CSRF and exempt from this requirement.
   - Retrieve a token anytime via `GET /api/v1/auth/csrf`.

---

## 3. Standard Error Envelope

All API errors return a uniform JSON envelope with machine-readable error codes:

```json
{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "Invalid credentials. Check your username/email and password.",
    "details": {}
  }
}
```

### Standard Error Codes
| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `BAD_REQUEST` | Malformed syntax or invalid query parameters |
| 401 | `AUTHENTICATION_REQUIRED` | Missing, expired, or invalid token/session |
| 403 | `FORBIDDEN` | Insufficient permissions for user or machine role |
| 403 | `CSRF_TOKEN_MISSING` / `CSRF_TOKEN_INVALID` | Missing or mismatched CSRF token |
| 404 | `NOT_FOUND` | Requested project, machine, or record does not exist |
| 409 | `CONFLICT` | Resource collision (duplicate email, machine role conflict) |
| 422 | `VALIDATION_ERROR` | Request payload failed schema or business validation |
| 429 | `RATE_LIMITED` | Too many requests in time window |
| 500 | `INTERNAL_ERROR` | Unhandled backend exception (logged with stacktrace) |
| 503 | `SERVICE_UNAVAILABLE` | Database or required subsystem is unreachable |

---

## 4. Response Conventions

### Timestamps
All timestamps are serialized in ISO 8601 UTC format with explicit timezone offsets:
```json
"createdAt": "2026-10-19T02:50:00+00:00"
```

### Field Naming
- Pydantic models serialize with **camelCase aliases** (`displayName`, `isActive`, `createdAt`) for seamless compatibility with the React TypeScript frontend (`frontenda/src/types/index.ts`).
- Backend Python models internally use idiomatic **snake_case** (`display_name`, `is_active`, `created_at`).

### Pagination Format
For list endpoints:
```json
{
  "items": [...],
  "total": 120,
  "limit": 20,
  "offset": 0,
  "hasNext": true
}
```

---

## 5. Security & Auditing Standards

- Plaintext passwords are **never logged**, **never stored**, and **never returned** in API responses.
- Hashes are generated using modern `bcrypt` with 12 salt rounds.
- All sensitive operations (`auth.register`, `auth.login`, `auth.logout`, `auth.password_change`, `machine.paired`, `role.changed`) create immutable records in the `audit_events` table with IP address and timestamp.
