# Multi-Machine Deployment, Operations, and Security Guide (Phase 10)

## 1. Overview
**ADC (Autonomous Distributed AI Trainer)** is designed for multi-machine distributed machine learning where:
- A **Master Workstation** coordinates training projects, inspects code, and monitors progress.
- Multiple **Volunteer Worker Nodes** contribute compute resources (CPU, RAM, GPU) to train models across local networks or the internet.

This guide provides operational instructions for deploying and running ADC across separate physical or virtual machines.

---

## 2. Machine 1: Central Coordinator & Master Workstation

The Coordinator host runs the PostgreSQL database, FastAPI ASGI server, WebSocket hub, and the Master Agent.

### Step 1: System Requirements & Dependencies
- **OS**: Linux (Ubuntu 22.04+), macOS, or Windows 11.
- **Python**: 3.11 or newer.
- **Docker**: For running PostgreSQL.
- **Open Inbound Firewall Ports**:
  - `8000`: FastAPI REST API and WebSocket hub (inbound TCP).
  - `29500` *(Optional)*: Required only if running native direct PyTorch DDP without Relay.

### Step 2: Database Initialization
On Machine 1:
```bash
cd backenda
docker compose up -d
```
Verify PostgreSQL is healthy on `localhost:5432`.

### Step 3: Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Key configuration values for Machine 1:
```env
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_URL=postgresql+asyncpg://adc:adc_dev_password@localhost:5432/adc_db
SECRET_KEY=<generate_random_64_character_key>
CORS_ORIGINS=http://localhost:5173,http://<machine-1-ip>:5173
STORAGE_ROOT=./storage
```

### Step 4: Apply Database Migrations & Start Backend
```bash
# Activate virtual environment
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Apply migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 5: Start the Master Agent
In a separate terminal on Machine 1:
```bash
adc-master
# or: python -m agents.master.launcher
```
1. The agent generates a 6-character pairing code (e.g., `M5X9P2`).
2. Open the web browser at `http://<machine-1-ip>:5173`.
3. In the pairing prompt, enter the 6-character code and select **Master Workstation**.
4. Machine 1 is now authenticated with an active Master role lease.

---

## 3. Machine 2+: Volunteer Worker Nodes

Worker nodes run the compute daemon that detects local hardware, joins projects via 9-digit codes, downloads training packages, and executes training steps in sandboxes.

### Step 1: Worker Requirements
- **OS**: Linux, Windows 10/11, or macOS.
- **Python**: 3.11+ with PyTorch installed.
- **Network**: Outbound internet/LAN access to Machine 1 on port 8000 over HTTP/HTTPS.
- **Inbound Ports**: **None required**. Workers connect outbound to the coordinator.

### Step 2: Install Worker Agent
On Machine 2:
```bash
git clone <repository-url>
cd adc/backenda

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

### Step 3: Run Worker Agent
Set the coordinator URL and start the worker daemon:
```bash
# Point to Machine 1 IP address
export ADC_BACKEND_URL=http://<machine-1-ip>:8000
# On Windows PowerShell:
# $env:ADC_BACKEND_URL = "http://<machine-1-ip>:8000"

adc-worker
# or: python -m agents.worker.launcher
```

### Step 4: Browser Pairing and Role Lease
1. The worker agent generates a 6-character code and displays:
   `[ADC Worker Agent] Pairing challenge code: W7K3R9`
2. In the browser, navigate to the pairing screen, enter `W7K3R9`, and select **Worker Node**.
3. Machine 2 is now paired and displays detected hardware in the dashboard.

### Step 5: Joining a Distributed Training Project
1. Master user puts a project online, generating a 9-digit code (e.g., `482-910-375`).
2. Worker user enters `482-910-375` in the **Join Project** screen.
3. Worker selects resource budgets (e.g., 4 CPU cores, 8 GB RAM, GPU enabled).
4. The worker agent automatically receives task leases, downloads code packages, executes training slices inside isolated sandboxes, and streams loss telemetry and checkpoints back to the coordinator.

---

## 4. Operational Maintenance & Storage Management

### Storage Backup & Retention
ADC writes all persistent artifacts to `STORAGE_ROOT` (`storage/`):
- `storage/datasets/`: Immutable uploaded datasets.
- `storage/packages/`: Immutable model training code packages.
- `storage/checkpoints/{project_id}/`: Validated PyTorch model checkpoints (`.pt`).
- `storage/logs/`: Application audit and execution logs.

**Recommended Backup Strategy**:
- Daily snapshot of the PostgreSQL database (`pg_dump`).
- Checkpoint deduplication: Keep the 5 most recent checkpoints per project and the final checkpoint.
- Temporary upload cleanup: Handled automatically by `SystemRecoveryService` (`POST /api/v1/system/recovery/sweep`).

### Credential & Key Rotation
- **Machine Identity Keys**: Stored in `~/.adc/machine_identity.json`. To rotate, stop the agent, delete this file, and restart. The agent generates a new Ed25519 keypair and requests re-pairing.
- **Session Secrets**: Set `SECRET_KEY` in `.env`. Rotating `SECRET_KEY` invalidates all existing user session JWTs and requires users to log in again.
- **Machine Role Revocation**: Project owners or machine operators can revoke role leases at any time via `POST /api/v1/machines/revoke`.

---

## 5. Security Boundaries & Threat Model

| Threat | Mitigation Mechanism |
|---|---|
| Malicious Package Code | Pre-execution AST scanner (`CodeSecurityScanner`) bans `ctypes`, dynamic `eval`, system calls, and sensitive paths. |
| Host Secret Exfiltration | Environment sanitization strips `AWS_*`, `DATABASE_*`, `SECRET_*`, and API keys before child process launch. |
| Pickling Vulnerabilities | All uploaded checkpoints are verified with `torch.load(..., weights_only=True)`. |
| ZipSlip Traversal | Archive extraction enforces path normalization and rejects files escaping destination directories. |
| Host Resource Exhaustion | `ResourceGuard` monitors host RAM and disk pressure, triggering safety pauses before host OS destabilization. |
