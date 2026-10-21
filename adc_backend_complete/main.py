"""ADC backend: project directory + WebRTC signaling service.

Local-development implementation compatible with ADC frontendb and adc_agent.py.

IMPORTANT:
- This service only brokers project discovery/signaling; it does not relay the
  WebRTC data channel when a direct ICE path succeeds.
- SQLite is suitable for local development and a single backend process.
- Before public deployment, put it behind HTTPS/WSS, configure a strong
  ADC_REGISTRATION_TOKEN, add proper user/project authorization and monitoring,
  and use a managed database when running multiple backend replicas.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_VERSION = "1.0.0"
DB_PATH = Path(os.environ.get("ADC_BACKEND_DB", str(Path(__file__).with_name("adc_backend.sqlite3")))).resolve()
REGISTRATION_TOKEN = os.environ.get("ADC_REGISTRATION_TOKEN", "").strip()

DEFAULT_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5175", "http://127.0.0.1:5175",
    "http://localhost:4173", "http://127.0.0.1:4173",
]
ENV_ORIGINS = [x.strip() for x in os.environ.get("ADC_ALLOWED_ORIGINS", "").split(",") if x.strip()]

app = FastAPI(
    title="Autonomous Distributed AI Trainer API",
    version=APP_VERSION,
    description="Project lookup, join-code validation, and WebRTC signaling for ADC.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(set(DEFAULT_ORIGINS + ENV_ORIGINS)),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Installation-Id"],
)

_DB_LOCK = threading.RLock()
_RATE_LOCK = threading.Lock()
_RESOLVE_ATTEMPTS: dict[str, list[float]] = {}

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  data_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  active_code TEXT UNIQUE,
  accepting_workers INTEGER NOT NULL DEFAULT 0,
  master_agent_id TEXT,
  connection_token TEXT,
  public_ip TEXT,
  master_port INTEGER,
  protocol TEXT,
  master_hostname TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  registered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_projects_code ON projects(active_code);
CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  role TEXT NOT NULL,
  registered_at TEXT NOT NULL,
  last_seen REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agents_project ON agents(project_id);
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_agent_id TEXT NOT NULL,
  from_agent_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  project_id TEXT NOT NULL,
  sdp TEXT NOT NULL,
  auth_token TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_target ON signals(target_agent_id, created_at);
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  connected INTEGER NOT NULL DEFAULT 1,
  last_seen REAL NOT NULL,
  PRIMARY KEY(worker_id, project_id)
);
CREATE TABLE IF NOT EXISTS machine_settings (
  installation_id TEXT PRIMARY KEY,
  settings_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS machines (
  installation_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  platform TEXT,
  public_key TEXT,
  registered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pairing_challenges (
  pairing_code TEXT PRIMARY KEY,
  installation_id TEXT NOT NULL,
  expires_at REAL NOT NULL,
  used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  display_name TEXT NOT NULL,
  salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  username TEXT NOT NULL,
  expires_at REAL NOT NULL,
  created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    with _DB_LOCK:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.executescript(SCHEMA)
            # Demo login is used by the current frontend during local development.
            exists = conn.execute("SELECT 1 FROM users WHERE username = ?", ("researcher_demo",)).fetchone()
            if not exists:
                salt = secrets.token_bytes(16)
                pwd = hashlib.scrypt(b"Password123!", salt=salt, n=2**14, r=8, p=1).hex()
                conn.execute(
                    "INSERT INTO users(username,email,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?)",
                    ("researcher_demo", "researcher@adc-network.io", "Researcher Demo", salt.hex(), pwd, now_iso()),
                )
            conn.commit()
        finally:
            conn.close()


init_db()


# ─── Database serialization helpers ──────────────────────────────────────────

def digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def new_code(conn: sqlite3.Connection) -> str:
    for _ in range(250):
        candidate = f"{secrets.randbelow(1_000_000_000):09d}"
        used = conn.execute("SELECT 1 FROM projects WHERE active_code = ?", (candidate,)).fetchone()
        if not used:
            return candidate
    raise HTTPException(503, "Could not create a unique project code. Please retry.")


def row_to_project(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = json.loads(row["data_json"] or "{}")
    data.update({
        "id": row["id"], "status": row["status"], "active_code": row["active_code"],
        "accepting_workers": bool(row["accepting_workers"]), "masterAgentId": row["master_agent_id"],
        "connectionToken": row["connection_token"], "publicIp": row["public_ip"],
        "masterPort": row["master_port"], "protocol": row["protocol"],
        "masterHostname": row["master_hostname"], "created_at": row["created_at"],
        "updated_at": row["updated_at"], "registeredAt": row["registered_at"],
    })
    return data


def public_project(project: dict[str, Any]) -> dict[str, Any]:
    hidden = {"connectionToken", "masterAgentId", "publicIp", "masterPort", "protocol", "masterHostname", "workerAgentIds"}
    return {key: value for key, value in project.items() if key not in hidden}


def get_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any] | None:
    return row_to_project(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


def save_project(conn: sqlite3.Connection, p: dict[str, Any]) -> None:
    data_keys = {
        k: v for k, v in p.items()
        if k not in {
            "id", "status", "active_code", "accepting_workers", "masterAgentId", "connectionToken",
            "publicIp", "masterPort", "protocol", "masterHostname", "created_at", "updated_at", "registeredAt",
        }
    }
    conn.execute(
        """INSERT INTO projects(id,data_json,status,active_code,accepting_workers,master_agent_id,connection_token,
             public_ip,master_port,protocol,master_hostname,created_at,updated_at,registered_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET data_json=excluded.data_json,status=excluded.status,
             active_code=excluded.active_code,accepting_workers=excluded.accepting_workers,
             master_agent_id=excluded.master_agent_id,connection_token=excluded.connection_token,
             public_ip=excluded.public_ip,master_port=excluded.master_port,protocol=excluded.protocol,
             master_hostname=excluded.master_hostname,updated_at=excluded.updated_at,registered_at=excluded.registered_at""",
        (
            str(p["id"]), json.dumps(data_keys, separators=(",", ":")), str(p.get("status", "draft")),
            p.get("active_code"), int(bool(p.get("accepting_workers", False))), p.get("masterAgentId"),
            p.get("connectionToken"), p.get("publicIp"), p.get("masterPort"), p.get("protocol"),
            p.get("masterHostname"), str(p.get("created_at") or now_iso()), now_iso(), p.get("registeredAt"),
        ),
    )


def project_by_code(conn: sqlite3.Connection, code: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM projects WHERE active_code = ?", (code,)).fetchone()
    return row_to_project(row)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_resolve_rate_limit(request: Request) -> None:
    """In-process brute-force protection; production deployments should also rate-limit at the proxy."""
    key = _client_key(request)
    now = time.time()
    with _RATE_LOCK:
        recent = [t for t in _RESOLVE_ATTEMPTS.get(key, []) if now - t < 60]
        if len(recent) >= 20:
            _RESOLVE_ATTEMPTS[key] = recent
            raise HTTPException(429, "Too many project-code attempts. Wait a minute and retry.")
        recent.append(now)
        _RESOLVE_ATTEMPTS[key] = recent


def require_registration_token(authorization: str | None) -> None:
    """Optional shared secret for machine-to-backend writes; unset is for local development only."""
    expected = REGISTRATION_TOKEN
    if not expected:
        return
    token = ""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value.strip()
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Invalid or missing ADC registration token")


def emit_event(event: dict[str, Any]) -> None:
    event_hub.publish_from_sync(event)


# ─── Models ──────────────────────────────────────────────────────────────────
class AuthBody(BaseModel):
    username: str = Field(default="researcher_demo", min_length=1, max_length=80)
    password: str = Field(default="Password123!", min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    display_name: str | None = Field(default=None, max_length=100)


class CreateProjectBody(BaseModel):
    name: str = Field(default="Distributed Training Job", min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    dataset_name: str = Field(default="dataset.zip", max_length=255)
    dataset_size: str = Field(default="500 MB", max_length=100)
    code_file_name: str = Field(default="train.py", max_length=255)
    code_file_size: str = Field(default="12 KB", max_length=100)
    training_objective: str = Field(default="Distributed model training", max_length=500)
    model_architecture: str = Field(default="Diffusion model", max_length=500)
    visibility: str = Field(default="public", max_length=40)
    training_strategy: str = Field(default="data_parallel", max_length=80)
    workers_needed: int = Field(default=4, ge=1, le=1000)
    requirements: dict[str, Any] = Field(default_factory=dict)
    training_config: dict[str, Any] = Field(default_factory=dict)


class ResolveCodeBody(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class MasterRegisterBody(BaseModel):
    agentId: str = Field(min_length=1, max_length=200)
    projectId: str | None = Field(default=None, max_length=200)
    role: str = "master"
    publicIp: str | None = Field(default=None, max_length=100)
    masterPort: int | None = Field(default=None, ge=1, le=65535)
    hostname: str | None = Field(default=None, max_length=255)
    protocol: str = Field(default="ws", max_length=10)
    connectionToken: str = Field(min_length=16, max_length=500)
    agentVersion: str | None = None
    supportsWebRTC: bool = True
    connectionMode: str | None = None
    signalingProtocol: str | None = None


class SignalBody(BaseModel):
    targetAgentId: str = Field(min_length=1, max_length=200)
    fromAgentId: str = Field(min_length=1, max_length=200)
    signalId: str = Field(min_length=1, max_length=200)
    signalType: str = Field(min_length=1, max_length=20)
    sdp: str = Field(min_length=1, max_length=250_000)
    projectId: str = Field(min_length=1, max_length=200)
    authToken: str = Field(min_length=1, max_length=500)


class WorkerUpdateBody(BaseModel):
    agentId: str | None = None
    projectId: str | None = None
    worker: dict[str, Any] = Field(default_factory=dict)
    event: str = "worker_connected"


# ─── Live dashboard events ───────────────────────────────────────────────────
class EventHub:
    def __init__(self) -> None:
        self.clients: dict[WebSocket, str | None] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.loop = asyncio.get_running_loop()
        async with self.lock:
            self.clients[ws] = None
        await ws.send_json({"type": "connected", "service": "adc-backend", "version": APP_VERSION})

    async def subscribe(self, ws: WebSocket, project_id: str | None) -> None:
        async with self.lock:
            if ws in self.clients:
                self.clients[ws] = project_id
        await ws.send_json({"type": "subscribed", "projectId": project_id})

    async def disconnect(self, ws: WebSocket) -> None:
        async with self.lock:
            self.clients.pop(ws, None)

    async def broadcast(self, event: dict[str, Any]) -> None:
        project_id = event.get("projectId") or event.get("project_id")
        async with self.lock:
            recipients = [ws for ws, subscribed in self.clients.items() if subscribed is None or str(subscribed) == str(project_id)]
        for ws in recipients:
            try:
                await ws.send_json(event)
            except Exception:
                await self.disconnect(ws)

    def publish_from_sync(self, event: dict[str, Any]) -> None:
        loop = self.loop
        if loop and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.broadcast(event), loop)
            except RuntimeError:
                pass


event_hub = EventHub()


# ─── Health and lightweight demo authentication ───────────────────────────────
@app.get("/")
def root() -> dict[str, Any]:
    return {"service": "ADC backend", "version": APP_VERSION, "health": "/health", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
        database = "ok"
    except sqlite3.Error:
        database = "error"
    return {"status": "ok" if database == "ok" else "degraded", "database": database, "version": APP_VERSION}


@app.get("/api/v1/auth/csrf")
def csrf() -> dict[str, str]:
    # API clients currently use this header as a handshake. Cookie-based auth is not used by this app.
    return {"csrf_token": "adc-local-csrf-v1"}


def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1).hex()


def _issue_session(conn: sqlite3.Connection, username: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn.execute("INSERT INTO sessions(token_hash,username,expires_at,created_at) VALUES(?,?,?,?)",
                 (token_hash, username, time.time() + 30 * 24 * 3600, now_iso()))
    return token


@app.post("/api/v1/auth/login")
def login(body: AuthBody) -> dict[str, Any]:
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
        if not user:
            raise HTTPException(401, "Invalid username or password")
        if not hmac.compare_digest(_hash_password(body.password, user["salt"]), user["password_hash"]):
            raise HTTPException(401, "Invalid username or password")
        token = _issue_session(conn, body.username)
        return {"access_token": token, "token_type": "bearer", "user": {"id": "user-" + body.username, "username": body.username, "email": user["email"]}}


@app.post("/api/v1/auth/register")
def register(body: AuthBody) -> dict[str, Any]:
    username = body.username.strip()
    email = (body.email or f"{username}@local.test").strip()
    display_name = (body.display_name or username).strip()
    if not username:
        raise HTTPException(422, "Username is required")
    salt = secrets.token_bytes(16).hex()
    pwd_hash = _hash_password(body.password, salt)
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise HTTPException(409, "Username already exists; sign in instead")
        conn.execute("INSERT INTO users(username,email,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?)",
                     (username, email, display_name, salt, pwd_hash, now_iso()))
        token = _issue_session(conn, username)
    return {"access_token": token, "token_type": "bearer", "user": {"id": "user-" + username, "username": username, "email": email}}


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization:
        raise HTTPException(401, "Sign in first")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Invalid authorization header")
    token_hash = hashlib.sha256(token.strip().encode()).hexdigest()
    with db() as conn:
        row = conn.execute("SELECT s.username,s.expires_at,u.email,u.display_name FROM sessions s JOIN users u ON u.username=s.username WHERE s.token_hash = ?", (token_hash,)).fetchone()
        if not row or row["expires_at"] < time.time():
            raise HTTPException(401, "Session expired; sign in again")
        return {"id": "user-" + row["username"], "username": row["username"], "email": row["email"], "display_name": row["display_name"]}


@app.get("/api/v1/auth/me")
def me(user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    return user


# ─── Machine pairing and resource settings ────────────────────────────────────
@app.post("/api/v1/machines/register")
def register_machine(payload: dict[str, Any], user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    installation_id = str(payload.get("installation_id") or "").strip()
    if not installation_id:
        raise HTTPException(422, "installation_id is required")
    with db() as conn:
        conn.execute(
            "INSERT INTO machines(installation_id,name,platform,public_key,registered_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(installation_id) DO UPDATE SET name=excluded.name,platform=excluded.platform,public_key=excluded.public_key",
            (installation_id, str(payload.get("name") or "ADC machine")[:200], str(payload.get("platform") or "Unknown")[:100], str(payload.get("public_key") or "")[:500], now_iso()),
        )
    return {"id": "machine-" + installation_id[-12:], "installation_id": installation_id, "registered": True}


@app.post("/api/v1/machines/pairing/challenge")
def pairing_challenge(payload: dict[str, Any], user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    installation_id = str(payload.get("installation_id") or "").strip()
    if not installation_id:
        raise HTTPException(422, "installation_id is required")
    code = secrets.token_hex(4)
    with db() as conn:
        conn.execute("INSERT INTO pairing_challenges(pairing_code,installation_id,expires_at,used) VALUES(?,?,?,0)",
                     (code, installation_id, time.time() + 300))
    return {"pairing_code": code, "expires_in": 300}


@app.post("/api/v1/machines/pairing/complete")
def pairing_complete(payload: dict[str, Any], user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    code = str(payload.get("pairing_code") or "")
    role = str(payload.get("selected_role") or "")
    if role not in {"master", "worker"}:
        raise HTTPException(422, "selected_role must be master or worker")
    with db() as conn:
        challenge = conn.execute("SELECT * FROM pairing_challenges WHERE pairing_code=?", (code,)).fetchone()
        if not challenge or challenge["used"] or challenge["expires_at"] < time.time():
            raise HTTPException(400, "Pairing challenge is invalid or expired")
        conn.execute("UPDATE pairing_challenges SET used=1 WHERE pairing_code=?", (code,))
    return {"ok": True, "paired": True, "selected_role": role}


def _installation_id(request: Request) -> str:
    return (request.headers.get("X-Installation-Id") or "default-installation")[:200]


def _hardware_profile() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    total_ram = None
    available_ram = None
    disk_free = None
    try:
        import psutil
        vm = psutil.virtual_memory()
        total_ram = round(vm.total / (1024 ** 3), 2)
        available_ram = round(vm.available / (1024 ** 3), 2)
        disk_free = round(shutil.disk_usage(str(Path.home())).free / (1024 ** 3), 2)
    except Exception:
        try:
            disk_free = round(shutil.disk_usage(str(Path.home())).free / (1024 ** 3), 2)
        except Exception:
            pass
    gpu_name = "Not detected"
    gpu_mem = 0.0
    try:
        import subprocess
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout.strip():
            first = result.stdout.strip().splitlines()[0].split(",", 1)
            gpu_name = first[0].strip()
            if len(first) > 1:
                gpu_mem = round(float(first[1].strip()) / 1024, 2)
    except Exception:
        pass
    return {
        "cpuModel": os.environ.get("PROCESSOR_IDENTIFIER", "Detected by local agent"),
        "cpuCores": cpu_count,
        "ramTotalGB": total_ram,
        "ramAvailableGB": available_ram,
        "gpuModel": gpu_name,
        "gpuMemoryTotalGB": gpu_mem,
        "diskSpaceAvailableGB": disk_free,
    }


DEFAULT_SETTINGS = {"cpuCores": 1, "ramBudgetGB": 0.3, "gpuEnabled": False, "storageBudgetGB": 1, "globalPaused": False}


@app.get("/api/v1/resources/me")
def get_resources(request: Request, user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    installation_id = _installation_id(request)
    with db() as conn:
        row = conn.execute("SELECT settings_json FROM machine_settings WHERE installation_id=?", (installation_id,)).fetchone()
        settings = json.loads(row["settings_json"]) if row else dict(DEFAULT_SETTINGS)
    return {"hardwareProfile": _hardware_profile(), "contributionSettings": settings}


@app.patch("/api/v1/resources/me")
def update_resources(payload: dict[str, Any], request: Request, user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    installation_id = _installation_id(request)
    allowed = set(DEFAULT_SETTINGS)
    with db() as conn:
        row = conn.execute("SELECT settings_json FROM machine_settings WHERE installation_id=?", (installation_id,)).fetchone()
        settings = json.loads(row["settings_json"]) if row else dict(DEFAULT_SETTINGS)
        for key, value in payload.items():
            if key in allowed:
                settings[key] = value
        settings["cpuCores"] = max(0, int(settings.get("cpuCores", 1)))
        settings["ramBudgetGB"] = max(0.0, min(1_000_000.0, float(settings.get("ramBudgetGB", 0.3))))
        settings["storageBudgetGB"] = max(0.0, min(1_000_000.0, float(settings.get("storageBudgetGB", 1))))
        settings["gpuEnabled"] = bool(settings.get("gpuEnabled", False))
        settings["globalPaused"] = bool(settings.get("globalPaused", False))
        conn.execute("INSERT INTO machine_settings(installation_id,settings_json,updated_at) VALUES(?,?,?) "
                     "ON CONFLICT(installation_id) DO UPDATE SET settings_json=excluded.settings_json,updated_at=excluded.updated_at",
                     (installation_id, json.dumps(settings), now_iso()))
    return {"ok": True, "contributionSettings": settings}


# ─── Projects ────────────────────────────────────────────────────────────────
@app.get("/api/v1/projects")
def list_projects(my_projects: bool = Query(default=False), user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        projects = []
        for row in rows:
            p = row_to_project(row)
            worker_rows = conn.execute("SELECT worker_id,payload_json,connected,last_seen FROM workers WHERE project_id=? ORDER BY last_seen DESC", (p["id"],)).fetchall()
            workers = []
            for worker_row in worker_rows:
                payload = json.loads(worker_row["payload_json"] or "{}")
                details = payload.get("details") if isinstance(payload.get("details"), dict) else payload
                workers.append({
                    "machine_id": worker_row["worker_id"],
                    "machine_name": details.get("hostname") or details.get("machineName") or "worker-node",
                    "status": "computing" if worker_row["connected"] else "offline",
                    "cpu_cores_contributed": details.get("logicalCpuCores") or details.get("cpuCores") or 1,
                    "ram_contributed_gb": details.get("availableRamGB") or details.get("totalRamGB") or 0.3,
                    "gpu_enabled": details.get("gpuModel") not in (None, "None", "Not detected", ""),
                })
            safe = public_project(p)
            safe["workers"] = workers
            projects.append(safe)
    return {"projects": projects}


@app.post("/api/v1/projects")
def create_project(body: CreateProjectBody, user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    project_id = "project-" + uuid.uuid4().hex[:12]
    p = body.model_dump()
    p.update({"id": project_id, "status": "draft", "active_code": None, "accepting_workers": False, "created_at": now_iso()})
    with db() as conn:
        save_project(conn, p)
    return {"id": project_id, "project": public_project(p)}


@app.post("/api/v1/projects/{project_id}/online")
def online_project(project_id: str, user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        p = get_project(conn, project_id)
        if not p:
            raise HTTPException(404, "Project not found")
        if not p.get("active_code") or not p.get("accepting_workers"):
            p["active_code"] = new_code(conn)
        p["status"] = "online"
        p["accepting_workers"] = True
        save_project(conn, p)
    emit_event({"type": "project_online", "projectId": project_id, "data": {"projectCode": p["active_code"], "status": "online"}})
    return {"status": "online", "project_code": p["active_code"], "message": "Project is accepting workers", "project": public_project(p)}


@app.post("/api/v1/projects/{project_id}/{action}")
def project_action(project_id: str, action: str, user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    if action not in {"pause", "resume", "stop", "end"}:
        raise HTTPException(404, "Unknown project action")
    with db() as conn:
        p = get_project(conn, project_id)
        if not p:
            raise HTTPException(404, "Project not found")
        if action == "pause":
            p["status"] = "paused"
            p["accepting_workers"] = False
        elif action == "resume":
            p["status"] = "online"
            p["accepting_workers"] = True
            if not p.get("active_code"):
                p["active_code"] = new_code(conn)
        elif action == "stop":
            p["status"] = "stopped"
            p["accepting_workers"] = False
        else:
            p["status"] = "ended"
            p["accepting_workers"] = False
        save_project(conn, p)
    emit_event({"type": "project_status", "projectId": project_id, "data": {"status": p["status"]}})
    return {"ok": True, "status": p["status"], "project": public_project(p)}


def find_code_or_404(conn: sqlite3.Connection, code: str) -> dict[str, Any]:
    p = project_by_code(conn, code)
    if not p or not p.get("accepting_workers") or p.get("status") not in {"online", "training", "looking_for_workers"}:
        raise HTTPException(404, "Project code not found or project is not accepting workers")
    if not p.get("masterAgentId") or not p.get("connectionToken"):
        raise HTTPException(409, "The master agent has not registered yet. Start adc_agent.py in Master mode and retry.")
    return p


@app.post("/api/v1/projects/join-by-code")
def join_by_code(payload: dict[str, Any], request: Request, user: dict[str, Any] = __import__("fastapi").Depends(current_user)) -> dict[str, Any]:
    code = digits(payload.get("code"))
    if len(code) != 9:
        raise HTTPException(422, "Project code must contain exactly 9 digits")
    with db() as conn:
        p = find_code_or_404(conn, code)
        worker_id = "worker-" + uuid.uuid4().hex[:12]
        allocation = {
            "cpuCores": payload.get("cpuCores", 1), "ramGB": payload.get("ramGB", 0.3),
            "gpuEnabled": bool(payload.get("gpuEnabled", False)), "storageGB": payload.get("storageGB", 1),
            "joinedAt": now_iso(), "installationId": request.headers.get("X-Installation-Id"),
        }
        conn.execute("INSERT INTO workers(worker_id,project_id,payload_json,connected,last_seen) VALUES(?,?,?,?,?) "
                     "ON CONFLICT(worker_id,project_id) DO UPDATE SET payload_json=excluded.payload_json,connected=excluded.connected,last_seen=excluded.last_seen",
                     (worker_id, p["id"], json.dumps(allocation), 0, time.time()))
    return {"projectId": p["id"], "status": "joined", "contributionStatus": "active", "workerId": worker_id,
            "cpuCoresContributed": payload.get("cpuCores", 1), "ramContributedGB": payload.get("ramGB", 0.3),
            "gpuEnabled": bool(payload.get("gpuEnabled", False)), "storageBudgetGB": payload.get("storageGB", 1)}


# ─── Agent registration + WebRTC signaling ────────────────────────────────────
@app.post("/api/masters/register")
def register_master(body: MasterRegisterBody, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_registration_token(authorization)
    if body.role.lower() != "master":
        raise HTTPException(422, "role must be master")
    with db() as conn:
        project_id = str(body.projectId or "").strip()
        p = get_project(conn, project_id) if project_id else None
        if p is None:
            project_id = project_id or "project-" + uuid.uuid4().hex[:12]
            p = {
                "id": project_id, "name": body.hostname or "ADC Local Project", "description": "",
                "dataset_name": "dataset.zip", "dataset_size": "Not configured", "code_file_name": "train.py",
                "code_file_size": "Not configured", "training_objective": "Distributed training",
                "model_architecture": "Not specified", "visibility": "private", "training_strategy": "data_parallel",
                "workers_needed": 1, "requirements": {}, "training_config": {}, "status": "online",
                "active_code": new_code(conn), "accepting_workers": True, "created_at": now_iso(),
            }
        if not p.get("active_code"):
            p["active_code"] = new_code(conn)
        p["status"] = "online"
        p["accepting_workers"] = True
        p["masterAgentId"] = body.agentId
        p["connectionToken"] = body.connectionToken
        p["publicIp"] = body.publicIp
        p["masterPort"] = body.masterPort
        p["protocol"] = body.protocol
        p["masterHostname"] = body.hostname
        p["registeredAt"] = now_iso()
        save_project(conn, p)
        conn.execute("INSERT INTO agents(agent_id,project_id,role,registered_at,last_seen) VALUES(?,?,?,?,?) "
                     "ON CONFLICT(agent_id) DO UPDATE SET project_id=excluded.project_id,role=excluded.role,last_seen=excluded.last_seen",
                     (body.agentId, project_id, "master", now_iso(), time.time()))
    emit_event({"type": "master_registered", "projectId": project_id, "data": {"masterAgentId": body.agentId, "status": "online"}})
    return {"ok": True, "projectId": project_id, "agentId": body.agentId, "projectCode": p["active_code"], "status": "registered"}


@app.post("/api/webrtc/resolve-code")
def resolve_code(body: ResolveCodeBody, request: Request) -> dict[str, Any]:
    enforce_resolve_rate_limit(request)
    code = digits(body.code)
    if len(code) != 9:
        raise HTTPException(422, "Enter a valid 9-digit project code")
    with db() as conn:
        p = find_code_or_404(conn, code)
        # Compatible with the current agent: its master validates the project's shared connection token.
        return {"projectId": p["id"], "masterAgentId": p["masterAgentId"], "authToken": p["connectionToken"],
                "projectName": p.get("name", "ADC Project"), "transport": "webrtc-signaling"}


@app.post("/api/webrtc/signals")
def post_signal(body: SignalBody, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    signal_type = body.signalType.lower()
    if signal_type not in {"offer", "answer"}:
        raise HTTPException(400, "Only offer and answer are supported by this signaling protocol")
    with db() as conn:
        p = get_project(conn, body.projectId)
        if not p or not p.get("masterAgentId"):
            raise HTTPException(404, "Project or registered master not found")
        if not p.get("accepting_workers"):
            raise HTTPException(409, "Project is not accepting new workers")
        if not hmac.compare_digest(str(body.authToken), str(p.get("connectionToken") or "")):
            raise HTTPException(403, "Invalid project connection token")
        master_id = p["masterAgentId"]
        if signal_type == "offer":
            if body.targetAgentId != master_id or body.fromAgentId == master_id:
                raise HTTPException(400, "Offer must target this project's master from a worker agent")
            conn.execute("INSERT INTO agents(agent_id,project_id,role,registered_at,last_seen) VALUES(?,?,?,?,?) "
                         "ON CONFLICT(agent_id) DO UPDATE SET project_id=excluded.project_id,role='worker',last_seen=excluded.last_seen",
                         (body.fromAgentId, body.projectId, "worker", now_iso(), time.time()))
        else:
            if body.fromAgentId != master_id:
                raise HTTPException(403, "Only the registered master may publish an answer")
            target = conn.execute("SELECT project_id,role FROM agents WHERE agent_id=?", (body.targetAgentId,)).fetchone()
            if not target or target["project_id"] != body.projectId or target["role"] != "worker":
                raise HTTPException(404, "Worker has not submitted an offer for this project")
        conn.execute("DELETE FROM signals WHERE created_at < ?", (time.time() - 180,))
        conn.execute("INSERT INTO signals(target_agent_id,from_agent_id,signal_id,signal_type,project_id,sdp,auth_token,created_at) VALUES(?,?,?,?,?,?,?,?)",
                     (body.targetAgentId, body.fromAgentId, body.signalId, signal_type, body.projectId, body.sdp, body.authToken, time.time()))
        if signal_type == "offer":
            conn.execute("INSERT INTO workers(worker_id,project_id,payload_json,connected,last_seen) VALUES(?,?,?,?,?) "
                         "ON CONFLICT(worker_id,project_id) DO UPDATE SET last_seen=excluded.last_seen",
                         (body.fromAgentId, body.projectId, json.dumps({"workerId": body.fromAgentId, "status": "signaling"}), 0, time.time()))
    return {"ok": True, "queued": True, "signalId": body.signalId}


@app.get("/api/webrtc/signals/poll")
def poll_signals(agentId: str = Query(min_length=1, max_length=200), role: str = "worker", signalId: str | None = None) -> dict[str, Any]:
    role = role.lower()
    if role not in {"master", "worker"}:
        raise HTTPException(400, "role must be master or worker")
    with db() as conn:
        conn.execute("DELETE FROM signals WHERE created_at < ?", (time.time() - 180,))
        agent = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agentId,)).fetchone()
        if not agent or agent["role"] != role:
            raise HTTPException(403, "Unknown agent or role mismatch")
        conn.execute("UPDATE agents SET last_seen=? WHERE agent_id=?", (time.time(), agentId))
        sql = "SELECT * FROM signals WHERE target_agent_id=? AND signal_type=?"
        params: list[Any] = [agentId, "offer" if role == "master" else "answer"]
        if signalId:
            sql += " AND signal_id=?"
            params.append(signalId)
        sql += " ORDER BY id ASC LIMIT 50"
        rows = conn.execute(sql, params).fetchall()
        signals = [
            {"targetAgentId": row["target_agent_id"], "fromAgentId": row["from_agent_id"], "signalId": row["signal_id"],
             "signalType": row["signal_type"], "sdp": row["sdp"], "projectId": row["project_id"], "authToken": row["auth_token"]}
            for row in rows
        ]
        if rows:
            conn.executemany("DELETE FROM signals WHERE id=?", [(row["id"],) for row in rows])
    return {"signals": signals}


@app.post("/api/masters/workers/update")
def update_worker(body: WorkerUpdateBody, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_registration_token(authorization)
    project_id = str(body.projectId or "").strip()
    if not project_id:
        raise HTTPException(422, "projectId is required")
    with db() as conn:
        p = get_project(conn, project_id)
        if not p:
            raise HTTPException(404, "Project not found")
        if not body.agentId or body.agentId != p.get("masterAgentId"):
            raise HTTPException(403, "Only the registered master may publish worker updates")
        worker = body.worker or {}
        worker_id = str(worker.get("workerId") or "").strip()
        if not worker_id:
            raise HTTPException(422, "worker.workerId is required")
        is_connected = bool(worker.get("connected", True))
        conn.execute("INSERT INTO workers(worker_id,project_id,payload_json,connected,last_seen) VALUES(?,?,?,?,?) "
                     "ON CONFLICT(worker_id,project_id) DO UPDATE SET payload_json=excluded.payload_json,connected=excluded.connected,last_seen=excluded.last_seen",
                     (worker_id, project_id, json.dumps(worker), int(is_connected), time.time()))
    emit_event({"type": body.event or "worker_updated", "projectId": project_id, "data": {"worker": worker, "status": "online" if is_connected else "offline"}})
    return {"ok": True, "event": body.event, "workerId": worker_id}


@app.websocket("/api/v1/ws/events")
async def event_socket(websocket: WebSocket) -> None:
    await event_hub.connect(websocket)
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat", "time": time.time()})
                continue
            if isinstance(message, dict):
                action = message.get("action")
                if action == "subscribe":
                    project_id = message.get("project_id") or message.get("projectId")
                    await event_hub.subscribe(websocket, str(project_id) if project_id else None)
                elif action == "ping":
                    await websocket.send_json({"type": "pong", "time": time.time()})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await event_hub.disconnect(websocket)
