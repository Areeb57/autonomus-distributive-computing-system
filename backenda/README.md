# ADC Backend — Autonomous Distributed AI Trainer

Backend API and agent coordination server for the ADC platform.

## Prerequisites

- **Python 3.11+**
- **Docker** and **Docker Compose** (for PostgreSQL)
- A terminal / shell

## Quick Start

### 1. Start PostgreSQL

```bash
cd backenda
docker compose up -d
```

This starts PostgreSQL on `localhost:5432` with:
- User: `adc`
- Password: `adc_dev_password`
- Database: `adc_db`

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

### 3. Configure environment

Copy `.env.example` to `.env` and adjust values as needed:

```bash
cp .env.example .env
```

The defaults work with the Docker Compose PostgreSQL instance.

### 4. Apply database migrations

```bash
alembic upgrade head
```

### 5. Start the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

### 6. Verify

- **Health check:** `GET http://localhost:8000/health`
- **Readiness check:** `GET http://localhost:8000/health/ready`
- **API docs (dev only):** `http://localhost:8000/docs`

## Project Structure

```
backenda/
├── app/                    # FastAPI application
│   ├── main.py             # App factory and ASGI entrypoint
│   ├── core/               # Config, logging, security, exceptions
│   ├── api/                # Routes, dependencies, middleware
│   │   └── routes/         # Endpoint modules
│   └── database/           # SQLAlchemy base and session
├── agents/                 # Master/Worker agent code (future phases)
├── migrations/             # Alembic migration scripts
├── storage/                # Runtime file storage
│   ├── datasets/
│   ├── packages/
│   ├── checkpoints/
│   └── logs/
├── docs/                   # Documentation
├── pyproject.toml          # Python project config and dependencies
├── alembic.ini             # Alembic configuration
├── docker-compose.yml      # PostgreSQL for local dev
├── Dockerfile              # Production container image
├── .env.example            # Env var template
└── README.md               # This file
```

## API Endpoints

### Health (Phase 1)
| Method | Path            | Description          |
|--------|-----------------|----------------------|
| GET    | `/health`       | Liveness probe       |
| GET    | `/health/ready` | Readiness probe (DB) |

### Authentication & Account (Phase 2)
| Method | Path                         | Description                                    |
|--------|------------------------------|------------------------------------------------|
| POST   | `/api/v1/auth/register`       | Register new user account                      |
| POST   | `/api/v1/auth/login`          | Authenticate and receive JWT + session cookies |
| POST   | `/api/v1/auth/logout`         | Clear session cookies and deactivate session   |
| GET    | `/api/v1/auth/me`             | Get current user profile                       |
| PATCH  | `/api/v1/auth/me`             | Update display name or avatar                  |
| POST   | `/api/v1/auth/change-password`| Change password and revoke existing sessions   |
| POST   | `/api/v1/auth/refresh`        | Refresh JWT access/refresh token pair          |
| GET    | `/api/v1/auth/sessions`       | List active login sessions for current user    |
| DELETE | `/api/v1/auth/sessions/{id}`  | Revoke a specific active session               |
| GET    | `/api/v1/auth/csrf`           | Get CSRF token for Double-Submit Cookie flow   |

### Machine Registration & Pairing (Phase 3)
| Method | Path                              | Description                                         |
|--------|-----------------------------------|-----------------------------------------------------|
| POST   | `/api/v1/machines/register`        | Register machine installation ID and Ed25519 public key |
| GET    | `/api/v1/machines/me`              | Get paired machines for user or machine by ID       |
| POST   | `/api/v1/machines/pairing/challenge` | Agent generates 6-char pairing challenge code      |
| POST   | `/api/v1/machines/pairing/complete`  | Browser user binds machine and assigns Master/Worker role |
| POST   | `/api/v1/machines/heartbeat`       | Agent maintains active instance lease and telemetry |
| POST   | `/api/v1/machines/role-change`     | Controlled transition between Master and Worker     |
| POST   | `/api/v1/machines/revoke`          | Revoke machine credentials and disconnect           |

See [Machine Identity & Pairing Architecture](docs/machine-identity-and-pairing.md) for sequence diagrams and security invariants.

### Resource Management & Safety Guard (Phase 4)
| Method | Path                           | Description                                                |
|--------|--------------------------------|------------------------------------------------------------|
| GET    | `/api/v1/resources/me`         | Get hardware profile, contribution settings, cluster capacity |
| PATCH  | `/api/v1/resources/me`         | Update CPU/RAM/Storage budgets with physical limit checks  |
| POST   | `/api/v1/resources/me/pause-all`  | Pause all volunteer compute contributions across projects   |
| POST   | `/api/v1/resources/me/resume-all` | Resume volunteer compute contributions                     |

See [Hardware Detection & Resource Guard Architecture](docs/hardware-detection-and-resource-guard.md) for detection mechanics and safety thresholds.

### Projects, Uploads & Nine-Digit Join Codes (Phase 5)
| Method | Path                                          | Description                                                 |
|--------|-----------------------------------------------|-------------------------------------------------------------|
| POST   | `/api/v1/projects`                            | Create a new project with training config and requirements  |
| GET    | `/api/v1/projects`                            | List projects (public, unlisted, or `?my_projects=true`)   |
| GET    | `/api/v1/projects/{id}`                       | Get full project details, datasets, packages, and workers   |
| PATCH  | `/api/v1/projects/{id}`                       | Update project metadata (owner only)                        |
| POST   | `/api/v1/projects/{id}/online`                | Put project online; validates assets & generates 9-digit code |
| POST   | `/api/v1/projects/{id}/pause`                 | Pause training on project                                   |
| POST   | `/api/v1/projects/{id}/resume`                | Resume training on project                                  |
| POST   | `/api/v1/projects/{id}/stop`                  | Stop training on project                                    |
| POST   | `/api/v1/projects/{id}/end`                   | Conclude project and revoke join codes                      |
| POST   | `/api/v1/projects/join-by-code`               | Volunteer worker enters 9-digit code to join cluster        |
| GET    | `/api/v1/projects/{id}/membership`            | Query worker node membership status                         |
| PATCH  | `/api/v1/projects/{id}/membership/resources`  | Adjust worker resource allocation on project                |
| POST   | `/api/v1/projects/{id}/leave`                 | Worker voluntarily leaves project without halting cluster   |
| POST   | `/api/v1/projects/{id}/datasets`              | Stream upload dataset (.zip/.tar.gz) with SHA-256 validation|
| GET    | `/api/v1/projects/{id}/datasets`              | List uploaded datasets for project                          |
| GET    | `/api/v1/projects/{id}/datasets/{id}/download`| Download dataset package file stream                        |
| POST   | `/api/v1/projects/{id}/packages`              | Stream upload model code package, inspect entrypoint/manifest|
| GET    | `/api/v1/projects/{id}/packages`              | List uploaded model code packages for project               |
| GET    | `/api/v1/projects/{id}/packages/{id}/download`| Download model package file stream                          |
| GET    | `/api/v1/projects/{id}/progress`              | Get current training metrics and step progress              |
| GET    | `/api/v1/projects/{id}/workers`               | List connected worker nodes on project                      |

See [Projects, Uploads & Join Codes Architecture](docs/projects-uploads-and-project-codes.md) for sequence diagrams and security invariants.

### Checkpoints & Resumption (Phase 8)
| Method | Path                                          | Description                                                 |
|--------|-----------------------------------------------|-------------------------------------------------------------|
| POST   | `/api/v1/projects/{id}/checkpoints`           | Stream upload and validate checkpoint (.pt / .safetensors)  |
| GET    | `/api/v1/projects/{id}/checkpoints`           | List all checkpoints ordered by step descending             |
| GET    | `/api/v1/projects/{id}/checkpoints/latest`    | Retrieve latest validated checkpoint for training resumption|
| GET    | `/api/v1/projects/{id}/checkpoints/{cid}/download` | Stream download checkpoint weights binary              |
| POST   | `/api/v1/projects/{id}/checkpoints/{cid}/resume`   | Restore project training run to specific checkpoint step|

See [Diffusion Training & Checkpoints Architecture](docs/diffusion-training-and-checkpoints.md) for U-Net architecture, streaming integrity validation, and resumption workflows.

### Distributed Training Strategies & Relay (Phase 9)
| Method | Path                                          | Description                                                 |
|--------|-----------------------------------------------|-------------------------------------------------------------|
| GET    | `/api/v1/projects/{id}/distributed/strategies`| List available execution strategies & network requirements  |
| POST   | `/api/v1/projects/{id}/distributed/rendezvous`| Assign rank, world size, master IP/port, or relay sync URL |
| POST   | `/api/v1/projects/{id}/distributed/sync`      | Synchronous parameter/gradient AllReduce via Relay Aggregator|
| POST   | `/api/v1/projects/{id}/distributed/heartbeat` | Report rank liveness and step progress                      |
| GET    | `/api/v1/projects/{id}/distributed/status`    | Query active cluster world size, ranks, and health          |

See [Distributed Training Strategies & Relay Architecture](docs/distributed-training-strategies.md) for network topologies, NAT relay mechanics, pipeline parallelism, and rollback recovery.


### Scheduler, Agent Tasks & WebSockets (Phase 6)
| Method | Path                                          | Description                                                 |
|--------|-----------------------------------------------|-------------------------------------------------------------|
| GET    | `/api/v1/agent/tasks`                         | Worker queries assigned tasks or triggers auto-dispatch     |
| POST   | `/api/v1/agent/tasks/{id}/acknowledge`        | Worker acknowledges task and confirms lease start           |
| POST   | `/api/v1/agent/tasks/{id}/metrics`            | Worker reports step telemetry metrics (loss, speed, util)   |
| POST   | `/api/v1/agent/tasks/{id}/status`             | Worker updates task execution status (completed, failed)    |
| WS     | `/api/v1/ws/events` or `/ws/events`           | Real-time WebSocket stream for browser clients              |
| WS     | `/api/v1/ws/agent` or `/ws/agent`             | Bi-directional WebSocket control stream for CLI agents      |

### System, Recovery & Operations (Phase 10)
| Method | Path                                          | Description                                                 |
|--------|-----------------------------------------------|-------------------------------------------------------------|
| POST   | `/api/v1/system/recovery/sweep`               | Trigger administrative stale task & orphaned upload recovery|
| GET    | `/api/v1/system/health/detailed`              | Detailed cluster metrics, storage usage, and active tasks   |

See [Frontend Integration Guide](docs/frontend-integration.md) for full contract specifications and [Multi-Machine Deployment Guide](docs/multi-machine-deployment.md) for distributed setup.

## Running Agents

Launch the Master or Worker CLI agents:
```bash
# Master Agent (coordination workstation)
adc-master
# or: python -m agents.master.launcher

# Worker Agent (compute node)
adc-worker
# or: python -m agents.worker.launcher
```

## Running Tests

Run the backend test suite:
```bash
pytest -v
```

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1     | ✅ Done | Backend foundation, config, logging, health, DB connection |
| 2     | ✅ Done | Database schema (18 models), Alembic migration, authentication, session management |
| 3     | ✅ Done | Machine identity, Ed25519 cryptography, browser pairing, role enforcement, agent launchers |
| 4     | ✅ Done | Hardware detection, resource budgets, safety guard, global pause/resume |
| 5     | ✅ Done | Projects, uploads, package manifests, nine-digit join codes, worker joining |
| 6     | ✅ Done | Scheduler, WebSockets, state machines, task leases & recovery |
| 7     | ✅ Done | Secure training execution, AST security scanner, runner sandboxing, runtime adapters |
| 8     | ✅ Done | Real diffusion training, checkpoints, resumption, and large model file handling |
| 9     | ✅ Done | Distributed training strategies, relay aggregator, rendezvous, and pipeline model parallelism |
| 10    | ✅ Done | Full integration, fault-recovery, production readiness, and operational documentation |

## Frontend

The React frontend is in `frontenda/` (Vite + React 19 + TypeScript).
Frontend API contracts and integration guides are documented in [docs/frontend-integration.md](docs/frontend-integration.md).
Multi-machine operational deployment is documented in [docs/multi-machine-deployment.md](docs/multi-machine-deployment.md).

