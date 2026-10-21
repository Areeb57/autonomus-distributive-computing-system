"""ADC local development backend.

This is a local prototype for testing project codes and WebRTC signaling.
It intentionally keeps records in memory; restart clears projects and signals.
Do not expose this unauthenticated development service to the public internet.
"""
from __future__ import annotations

import asyncio
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="ADC Local Backend", version="0.1.0", description="Local development API for ADC project registration and WebRTC signaling.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
        "http://localhost:5175", "http://127.0.0.1:5175",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_LOCK = threading.RLock()
_PROJECTS: dict[str, dict[str, Any]] = {}
_MASTERS: dict[str, dict[str, Any]] = {}
_SIGNALS: dict[str, list[dict[str, Any]]] = {}
_WORKER_UPDATES: dict[str, dict[str, dict[str, Any]]] = {}
_USERS = {"researcher_demo": {"id": "user-local-demo", "username": "researcher_demo", "email": "researcher@adc-network.io"}}
_MACHINE_SETTINGS: dict[str, Any] = {
    "cpuCores": 2,
    "ramBudgetGB": 0.3,
    "gpuEnabled": False,
    "storageBudgetGB": 2,
    "globalPaused": False,
}


def _digits(code: Any) -> str:
    return "".join(ch for ch in str(code or "") if ch.isdigit())


def _new_code() -> str:
    for _ in range(100):
        candidate = f"{secrets.randbelow(1_000_000_000):09d}"
        if all(project.get("active_code") != candidate for project in _PROJECTS.values()):
            return candidate
    raise RuntimeError("Could not allocate a unique project code")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_public(p: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in p.items() if k not in {"connectionToken", "masterAgentId", "publicIp", "masterPort", "workerAgentIds"}}


class LoginBody(BaseModel):
    username: str = "researcher_demo"
    password: str = "Password123!"
    email: str | None = None
    display_name: str | None = None


class CreateProjectBody(BaseModel):
    name: str = "Distributed Training Job"
    description: str = ""
    dataset_name: str = "dataset.zip"
    dataset_size: str = "500 MB"
    code_file_name: str = "train.py"
    code_file_size: str = "12 KB"
    training_objective: str = "Distributed model training"
    model_architecture: str = "Diffusion model"
    visibility: str = "public"
    training_strategy: str = "data_parallel"
    workers_needed: int = 4
    requirements: dict[str, Any] = Field(default_factory=dict)
    training_config: dict[str, Any] = Field(default_factory=dict)


class ResolveCodeBody(BaseModel):
    code: str


class MasterRegisterBody(BaseModel):
    agentId: str
    projectId: str | None = None
    role: str = "master"
    publicIp: str | None = None
    masterPort: int | None = None
    hostname: str | None = None
    protocol: str = "ws"
    connectionToken: str
    agentVersion: str | None = None
    supportsWebRTC: bool = True
    connectionMode: str | None = None
    signalingProtocol: str | None = None


class SignalBody(BaseModel):
    targetAgentId: str
    fromAgentId: str
    signalId: str
    signalType: str
    sdp: str
    projectId: str
    authToken: str


class WorkerUpdateBody(BaseModel):
    agentId: str | None = None
    projectId: str | None = None
    worker: dict[str, Any] = Field(default_factory=dict)
    event: str = "worker_connected"


@app.get("/")
def root():
    return {"service": "ADC local backend", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "adc-local-backend", "version": "0.1.0"}


@app.get("/api/v1/auth/csrf")
def csrf():
    return {"csrf_token": "local-development-csrf-token"}


@app.post("/api/v1/auth/login")
def login(body: LoginBody):
    user = _USERS.setdefault(body.username, {"id": "user-" + uuid.uuid4().hex[:8], "username": body.username, "email": body.email or f"{body.username}@local.test"})
    return {"access_token": "local-dev-token-" + body.username, "token_type": "bearer", "user": user}


@app.post("/api/v1/auth/register")
def register(body: LoginBody):
    username = body.username or "researcher_demo"
    user = _USERS.setdefault(username, {"id": "user-" + uuid.uuid4().hex[:8], "username": username, "email": body.email or f"{username}@local.test"})
    return {"access_token": "local-dev-token-" + username, "token_type": "bearer", "user": user}


@app.get("/api/v1/auth/me")
def me():
    return {"id": "user-local-demo", "username": "researcher_demo", "email": "researcher@adc-network.io"}


@app.post("/api/v1/machines/register")
def register_machine(payload: dict[str, Any]):
    install_id = str(payload.get("installation_id") or uuid.uuid4())
    return {"id": "machine-" + install_id[-12:], "installation_id": install_id, "registered": True}


@app.post("/api/v1/machines/pairing/challenge")
def pairing_challenge(payload: dict[str, Any]):
    return {"pairing_code": secrets.token_hex(4), "expires_in": 300}


@app.post("/api/v1/machines/pairing/complete")
def pairing_complete(payload: dict[str, Any]):
    return {"ok": True, "paired": True, "selected_role": payload.get("selected_role")}


@app.get("/api/v1/resources/me")
def get_resources():
    import os
    total_ram = 8.0
    available_ram = 4.0
    try:
        import psutil  # optional
        vm = psutil.virtual_memory()
        total_ram = round(vm.total / (1024**3), 2)
        available_ram = round(vm.available / (1024**3), 2)
    except Exception:
        pass
    return {
        "hardwareProfile": {
            "cpuModel": "Detected by local agent",
            "cpuCores": os.cpu_count() or 2,
            "ramTotalGB": total_ram,
            "ramAvailableGB": available_ram,
            "gpuModel": "None",
            "gpuMemoryTotalGB": 0,
            "diskSpaceAvailableGB": 20,
        },
        "contributionSettings": dict(_MACHINE_SETTINGS),
    }


@app.patch("/api/v1/resources/me")
def update_resources(payload: dict[str, Any]):
    with _LOCK:
        mapping = {
            "cpuCores": "cpuCores", "ramBudgetGB": "ramBudgetGB",
            "gpuEnabled": "gpuEnabled", "storageBudgetGB": "storageBudgetGB",
            "globalPaused": "globalPaused",
        }
        for incoming, target in mapping.items():
            if incoming in payload:
                _MACHINE_SETTINGS[target] = payload[incoming]
        return {"ok": True, "contributionSettings": dict(_MACHINE_SETTINGS)}


@app.get("/api/v1/projects")
def list_projects(my_projects: bool = Query(default=False)):
    with _LOCK:
        items = []
        for project in _PROJECTS.values():
            p = _project_public(project)
            p["workers"] = [
                {
                    "machine_id": w.get("workerId", "worker"),
                    "machine_name": w.get("details", {}).get("hostname", "worker-node"),
                    "status": "computing" if w.get("connected") else "offline",
                    "cpu_cores_contributed": w.get("details", {}).get("logicalCpuCores", 1) or 1,
                    "ram_contributed_gb": w.get("details", {}).get("availableRamGB", 0.3) or 0.3,
                    "gpu_enabled": w.get("details", {}).get("gpuModel") not in (None, "None", "Not detected"),
                }
                for w in _WORKER_UPDATES.get(project["id"], {}).values()
            ]
            items.append(p)
    return {"projects": items}


@app.post("/api/v1/projects")
def create_project(body: CreateProjectBody):
    project_id = "project-" + uuid.uuid4().hex[:12]
    project = {
        "id": project_id,
        "name": body.name,
        "description": body.description,
        "dataset_name": body.dataset_name,
        "dataset_size": body.dataset_size,
        "code_file_name": body.code_file_name,
        "code_file_size": body.code_file_size,
        "training_objective": body.training_objective,
        "model_architecture": body.model_architecture,
        "visibility": body.visibility,
        "training_strategy": body.training_strategy,
        "workers_needed": body.workers_needed,
        "requirements": body.requirements,
        "training_config": body.training_config,
        "status": "draft",
        "active_code": None,
        "created_at": _now(),
        "masterAgentId": None,
        "connectionToken": None,
        "publicIp": None,
        "masterPort": None,
        "workerAgentIds": set(),
    }
    with _LOCK:
        _PROJECTS[project_id] = project
    return {"id": project_id, "project": _project_public(project)}


@app.post("/api/v1/projects/{project_id}/online")
def online_project(project_id: str):
    with _LOCK:
        project = _PROJECTS.get(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        if not project.get("active_code"):
            project["active_code"] = _new_code()
        project["status"] = "online"
        project["accepting_workers"] = True
        return {
            "status": "online",
            "project_code": project["active_code"],
            "message": "Project is accepting workers",
            "project": _project_public(project),
        }


@app.post("/api/v1/projects/{project_id}/{action}")
def project_action(project_id: str, action: str):
    if action not in {"pause", "resume", "stop", "end"}:
        raise HTTPException(404, "Unknown project action")
    with _LOCK:
        project = _PROJECTS.get(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        if action == "pause":
            project["status"] = "paused"
        elif action == "resume":
            project["status"] = "online"
        elif action == "stop":
            project["status"] = "stopped"
        else:
            project["status"] = "ended"
            project["accepting_workers"] = False
        return {"ok": True, "status": project["status"], "project": _project_public(project)}


@app.post("/api/v1/projects/join-by-code")
def join_by_code(payload: dict[str, Any]):
    code = _digits(payload.get("code"))
    if len(code) != 9:
        raise HTTPException(422, "Project code must contain exactly 9 digits")
    with _LOCK:
        project = next((p for p in _PROJECTS.values() if p.get("active_code") == code), None)
        if not project or not project.get("accepting_workers", False):
            raise HTTPException(404, "Project code not found or not accepting workers")
        if not project.get("masterAgentId") or not project.get("connectionToken"):
            raise HTTPException(409, "Master agent is not registered yet. Start adc_agent.py in Master mode and retry.")
        worker_id = "worker-" + uuid.uuid4().hex[:8]
        project.setdefault("joins", []).append({"workerId": worker_id, "joinedAt": _now(), "allocation": payload})
        return {
            "projectId": project["id"], "status": "joined", "contributionStatus": "active",
            "cpuCoresContributed": payload.get("cpuCores", 1),
            "ramContributedGB": payload.get("ramGB", 0.3),
            "gpuEnabled": bool(payload.get("gpuEnabled", False)),
            "storageBudgetGB": payload.get("storageGB", 2),
        }


@app.post("/api/masters/register")
def register_master(body: MasterRegisterBody):
    with _LOCK:
        project_id = str(body.projectId or "").strip()
        project = _PROJECTS.get(project_id) if project_id else None
        # Useful for stand-alone local agent testing when the master was started without UI project creation.
        if project is None:
            project_id = project_id or "project-" + uuid.uuid4().hex[:12]
            project = {
                "id": project_id, "name": body.hostname or "Local ADC Test Project", "description": "",
                "dataset_name": "dataset.zip", "dataset_size": "Local test", "code_file_name": "train.py",
                "code_file_size": "Local test", "status": "online", "active_code": _new_code(),
                "created_at": _now(), "accepting_workers": True, "masterAgentId": None,
                "connectionToken": None, "publicIp": None, "masterPort": None, "workerAgentIds": set(),
            }
            _PROJECTS[project_id] = project
        project["masterAgentId"] = body.agentId
        project["connectionToken"] = body.connectionToken
        project["publicIp"] = body.publicIp
        project["masterPort"] = body.masterPort
        project["protocol"] = body.protocol
        project["masterHostname"] = body.hostname
        project["registeredAt"] = _now()
        _MASTERS[body.agentId] = {"projectId": project_id, "registeredAt": _now()}
        return {"ok": True, "projectId": project_id, "agentId": body.agentId, "projectCode": project.get("active_code")}


@app.post("/api/webrtc/resolve-code")
def resolve_code(body: ResolveCodeBody):
    code = _digits(body.code)
    if len(code) != 9:
        raise HTTPException(422, "Enter a 9-digit project code")
    with _LOCK:
        project = next((p for p in _PROJECTS.values() if p.get("active_code") == code), None)
        if not project or not project.get("accepting_workers", False):
            raise HTTPException(404, "Project code not found or not accepting workers")
        if not project.get("masterAgentId") or not project.get("connectionToken"):
            raise HTTPException(409, "Master is not registered. Select Master in adc_agent.py and try again.")
        return {
            "projectId": project["id"],
            "masterAgentId": project["masterAgentId"],
            # Current adc_agent.py expects the master's connection token here.
            # This is for localhost development only; replace with worker-scoped credentials for production.
            "authToken": project["connectionToken"],
            "projectName": project.get("name", "ADC Project"),
        }


@app.post("/api/webrtc/signals")
def post_signal(body: SignalBody):
    signal_type = body.signalType.lower()
    if signal_type not in {"offer", "answer"}:
        raise HTTPException(400, "Only offer and answer signal types are supported by this local prototype")
    with _LOCK:
        project = _PROJECTS.get(body.projectId)
        if not project or not project.get("masterAgentId"):
            raise HTTPException(404, "Project or registered master not found")
        if not secrets.compare_digest(str(body.authToken), str(project.get("connectionToken") or "")):
            raise HTTPException(403, "Invalid project connection token")
        master_id = project["masterAgentId"]
        if signal_type == "offer":
            if body.targetAgentId != master_id:
                raise HTTPException(400, "Offer target must be the project's master agent")
            project.setdefault("workerAgentIds", set()).add(body.fromAgentId)
        else:
            if body.fromAgentId != master_id:
                raise HTTPException(403, "Only the registered master can send an answer")
            if body.targetAgentId not in project.get("workerAgentIds", set()):
                raise HTTPException(404, "Answer recipient has not submitted an offer")
        item = {
            "targetAgentId": body.targetAgentId, "fromAgentId": body.fromAgentId,
            "signalId": body.signalId, "signalType": signal_type, "sdp": body.sdp,
            "projectId": body.projectId, "authToken": body.authToken,
            "createdAt": time.time(),
        }
        _SIGNALS.setdefault(body.targetAgentId, []).append(item)
        return {"ok": True, "queued": True, "signalId": body.signalId}


@app.get("/api/webrtc/signals/poll")
def poll_signals(agentId: str, role: str = "worker", signalId: str | None = None):
    role = role.lower()
    if role not in {"master", "worker"}:
        raise HTTPException(400, "role must be master or worker")
    with _LOCK:
        master = _MASTERS.get(agentId)
        if role == "master" and not master:
            raise HTTPException(403, "Unknown master agent")
        queued = _SIGNALS.get(agentId, [])
        now = time.time()
        # Drop stale signaling records after 2 minutes.
        queued = [item for item in queued if now - item.get("createdAt", now) < 120]
        selected = []
        retained = []
        for item in queued:
            if signalId and item.get("signalId") != signalId:
                retained.append(item)
            elif role == "master" and item.get("signalType") != "offer":
                retained.append(item)
            else:
                selected.append(item)
        _SIGNALS[agentId] = retained
        return {"signals": [{k: v for k, v in item.items() if k != "targetAgentId" and k != "createdAt"} for item in selected]}


@app.post("/api/masters/workers/update")
def update_worker(body: WorkerUpdateBody):
    with _LOCK:
        project = _PROJECTS.get(str(body.projectId or ""))
        if not project:
            raise HTTPException(404, "Project not found")
        if body.agentId and project.get("masterAgentId") and body.agentId != project.get("masterAgentId"):
            raise HTTPException(403, "Only this project's registered master can publish worker updates")
        worker = body.worker or {}
        worker_id = str(worker.get("workerId") or uuid.uuid4())
        _WORKER_UPDATES.setdefault(project["id"], {})[worker_id] = worker
        return {"ok": True, "event": body.event, "workerId": worker_id}


@app.websocket("/api/v1/ws/events")
async def event_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "connected", "service": "adc-local-backend"})
        while True:
            # This is only a local demo stream; worker/master details are polled from REST in this prototype.
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=25)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat", "time": time.time()})
    except WebSocketDisconnect:
        return
