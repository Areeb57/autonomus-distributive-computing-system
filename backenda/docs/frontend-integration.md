# Frontend Integration Guide (Phase 10)

## 1. Overview
The ADC platform provides a decoupled architecture:
- **Frontend** (`frontenda/`): React 19 + TypeScript + Vite. Uses interactive components, visualizations, and local-storage defaults.
- **Backend** (`backenda/`): FastAPI + PostgreSQL + SQLAlchemy 2.x + WebSockets + PyTorch + Ed25519 identity.

This document provides the integration guide, API contract mapping, WebSocket schemas, and instructions for connecting `frontenda/` to `backenda/` without rewriting the frontend UI.

---

## 2. API Contract Mapping

All backend endpoints are prefixed with `/api/v1`. The backend models use camelCase JSON aliases to match the TypeScript interfaces in `frontenda/src/types/index.ts`.

### A. Authentication & User Profile
- **Register**: `POST /api/v1/auth/register` (body: `email`, `username`, `displayName`, `password`)
- **Login**: `POST /api/v1/auth/login` (body: `username`, `password`)
  - Issues HTTP-only session cookies (`adc_session_id`, `adc_access_token`, `adc_csrf_token`) and returns bearer `access_token`.
- **Current User Profile**: `GET /api/v1/auth/me`
  - Returns `UserProfile`:
    ```json
    {
      "id": "uuid-string",
      "username": "antigravity_dev",
      "displayName": "Alex Mercer",
      "email": "alex.mercer@distributed-ai.local",
      "avatar": "https://..."
    }
    ```
- **CSRF Token**: `GET /api/v1/auth/csrf` (Double-Submit Cookie protection)

### B. Machine Identity & Pairing (One Machine, One Role)
- **Pairing Challenge**: `POST /api/v1/machines/pairing/challenge`
  - Agent generates 6-character code (e.g., `K9X2M4`).
- **Pairing Complete (Browser UI)**: `POST /api/v1/machines/pairing/complete`
  - Browser user enters 6-character code and chooses role (`master` or `worker`).
  - Sets active role lease and binds machine to current user.
- **Machine Status**: `GET /api/v1/machines/me`
  - Returns paired machines and active roles.

### C. Projects & Nine-Digit Join Codes
- **List Projects**: `GET /api/v1/projects` (optional query: `?my_projects=true`, `?visibility=public`)
  - Returns `ProjectListResponse` with an array of `ProjectDetailResponse` objects.
- **Get Project Details**: `GET /api/v1/projects/{id}`
  - Returns full project structure matching the frontend `Project` type, including `requirements`, `trainingConfig`, `workers`, `activeCode`, `metrics`, and `logs`.
- **Create Project**: `POST /api/v1/projects`
  - Accepts `ProjectCreateRequest` matching `Partial<Project>`.
- **Put Project Online**: `POST /api/v1/projects/{id}/online`
  - Validates uploaded dataset and model package, transitions status to `online`, and generates the canonical **9-digit project join code** (format: `XXX-XXX-XXX`).
- **Join by Code (Volunteer Worker)**: `POST /api/v1/projects/join-by-code`
  - Worker enters 9-digit code and allocated compute resources.
  - Automatically binds worker node to cluster.

### D. Hardware Detection & Resource Settings
- **Hardware Profile & Budget**: `GET /api/v1/resources/me`
  - Returns `HardwareProfile` (physical CPU cores, RAM GB, GPU model, VRAM GB) and `ContributionSettings`.
- **Update Resource Settings**: `PATCH /api/v1/resources/me`
  - Adjusts CPU core budget, RAM limit, GPU enablement, storage budget, and network preference. Enforces physical hardware ceiling validation.
- **Global Pause / Resume**:
  - `POST /api/v1/resources/me/pause-all`
  - `POST /api/v1/resources/me/resume-all`

---

## 3. Real-Time WebSocket Event Stream

The frontend subscribes to the persistent WebSocket stream at:
`ws://localhost:8000/api/v1/ws/events` (or `/ws/events`)

### Subscription Protocol
Upon opening the connection, the client sends:
```json
{
  "action": "subscribe",
  "project_id": "proj-uuid"
}
```

### Event Payloads Broadcast by Coordinator
1. **`training.progress`**:
   ```json
   {
     "type": "training.progress",
     "projectId": "proj-uuid",
     "data": {
       "step": 150,
       "totalSteps": 1000,
       "progressPercent": 15.0,
       "loss": 0.285,
       "speed": 12.4,
       "clusterCpuUtil": 45.2,
       "clusterGpuUtil": 88.0,
       "ramUtilGB": 5.4,
       "timestamp": "2026-10-19T04:00:00Z"
     }
   }
   ```
2. **`training.checkpoint`**:
   ```json
   {
     "type": "training.checkpoint",
     "projectId": "proj-uuid",
     "data": {
       "checkpointId": "ckpt-uuid",
       "step": 500,
       "loss": 0.182,
       "fileSizeBytes": 45892010,
       "downloadUrl": "/api/v1/projects/{id}/checkpoints/{cid}/download"
     }
   }
   ```
3. **`worker.joined`**:
   ```json
   {
     "type": "worker.joined",
     "projectId": "proj-uuid",
     "data": {
       "worker": {
         "id": "membership-uuid",
         "name": "Node-GTX4090",
         "status": "idle",
         "cpuCoresContributed": 8,
         "ramContributedGB": 16.0,
         "gpuModel": "NVIDIA GeForce RTX 4090",
         "gpuEnabled": true
       }
     }
   }
   ```
4. **`project.status_changed`**:
   ```json
   {
     "type": "project.status_changed",
     "projectId": "proj-uuid",
     "data": {
       "status": "training",
       "previousStatus": "online"
     }
   }
   ```

---

## 4. Frontend Integration Implementation Guide

To connect the React app in `frontenda/src/context/AppContext.tsx` to the backend without rewriting components:

### 1. Configure API Base URL in Frontend
Create `frontenda/.env`:
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

### 2. Connect `AppContext.tsx` Initial Load
In `frontenda/src/context/AppContext.tsx`:
- On mount (`useEffect`), issue `GET /api/v1/auth/me` and `GET /api/v1/projects`.
- If user is authenticated, populate `userProfile` and `projects` with data from the backend API.
- Fallback gracefully to local state if the backend is unreachable.

### 3. Connect Project Actions
- **`createProject`**: Submit `POST /api/v1/projects` with form values.
- **`joinProjectAsWorker`**: Submit `POST /api/v1/projects/join-by-code`.
- **`pauseProjectTraining` / `resumeProjectTraining`**: Call `POST /api/v1/projects/{id}/pause` and `POST /api/v1/projects/{id}/resume`.
- **`updateContributionSettings`**: Call `PATCH /api/v1/resources/me`.

### 4. WebSocket Listener
- When `activeProjectId` is set, open WebSocket connection to `/api/v1/ws/events`.
- On `training.progress` message, append point to `activeProject.metrics.history` and update `currentLoss`, `currentStep`, `progressPercent`.
