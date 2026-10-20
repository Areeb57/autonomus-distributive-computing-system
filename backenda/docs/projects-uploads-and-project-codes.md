# Projects, Streaming Uploads, and Nine-Digit Join Codes

This document details the project management architecture, streaming dataset and package uploads, archive safety checks, nine-digit join code mechanics, and the worker joining workflow for **ADC (Autonomous Distributed AI Trainer)**.

---

## 1. Project Creation & Lifecycle State Machine

Projects represent decentralized model training workloads defined by a Master machine user.

### State Transitions
```
                [Create Project]
                       │
                       ▼
                 draft / online
                       │
           [Put Project Online] (Requires verified dataset & package)
                       │
                       ▼
              looking_for_workers
                 │           ▲
   [Start Train] │           │ [Pause Train]
                 ▼           │
             training ───────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
   stopped              completed
(allocations released) (codes revoked)
```

- **`online` / `looking_for_workers`**: Assets are uploaded and verified; the project has an active 9-digit join code and accepts volunteer workers.
- **`training`**: Tasks are actively dispatched and executed across connected worker nodes.
- **`paused`**: Training is temporarily suspended; workers remain connected but pause active step computations.
- **`stopped`**: Training is halted; active worker allocations are released.
- **`completed`**: Training has achieved the target step count or was concluded by the owner; join codes are revoked.

---

## 2. Nine-Digit Project Join Codes

A project's join code allows volunteer workers to discover and join distributed workloads without exposing sensitive database IDs or master credentials.

### Properties & Generation Rules
- **Cryptographic Randomness**: Generated in [`app/core/project_code.py`](file:///d:/project/adc/backenda/app/core/project_code.py) via `secrets.randbelow(900_000_000) + 100_000_000`.
- **Display Pattern**: Formatted as `XXX-XXX-XXX` (e.g. `482-195-307`).
- **Input Normalization**: The API accepts both raw (`482195307`) and formatted (`482-195-307`) inputs, stripping whitespace and hyphens automatically.
- **Uniqueness & Retry Loop**: Collision check against `project_codes` table with automated collision retry logic.
- **Lifecycle Bound**: Join codes are revoked upon project completion (`POST /api/v1/projects/{id}/end`).

---

## 3. Streaming File Uploads & Archive Security

Handling multi-gigabyte datasets and user-submitted Python training archives requires strict resource and security boundaries implemented in [`app/core/upload.py`](file:///d:/project/adc/backenda/app/core/upload.py).

### A. Non-Buffering Streaming
Files are processed via `save_upload_stream`:
1. Chunks (1 MB default) are streamed directly from the incoming HTTP stream to a `.tmp` file in the project's designated storage directory.
2. An incremental SHA-256 hash (`hashlib.sha256()`) is computed during writing.
3. If the incoming stream exceeds `upload_max_size_mb`, the upload is aborted immediately, the temporary file is unlinked, and a `422 Unprocessable Content` error is returned.
4. On success, the temporary file is atomically renamed to its permanent path. Memory overhead remains constant ($O(1)$) regardless of file size.

### B. Archive Validation & ZipSlip Exploit Mitigation
Uploaded model training packages are inspected via `inspect_and_validate_package`:
1. **Path Traversal Check**: Scans internal archive paths before any extraction. If an archive contains path traversal indicators (`..` or leading `/`), the package is marked invalid with `is_validated = False` and rejected.
2. **Entrypoint Script Verification**: Verifies that the designated training script (default: `train.py`) exists within the archive.
3. **Manifest Extraction**: Inspects and parses `manifest.json` if included, capturing training framework, dependencies, and execution parameters.

---

## 4. Worker Joining Workflow (`POST /api/v1/projects/join-by-code`)

When a volunteer node enters a 9-digit project code:

1. **Authentication**: Confirms the worker's user session.
2. **Node Identification**: Resolves the worker's paired hardware via `X-Installation-Id` header or the user's paired machine record.
3. **Project Resolution**: Resolves the project by active 9-digit join code.
4. **Hardware Requirement Check**: Confirms the worker's contributed CPU cores and RAM satisfy `min_cpu_cores` and `min_ram_gb`.
5. **Membership & Allocation Persistence**: Creates or updates `ProjectMembership` and `ResourceAllocation` records.
6. **Independence**: A worker leaving (`POST /api/v1/projects/{id}/leave`) releases only its own compute allocation and does not disrupt other cluster nodes or terminate the project.

---

## 5. REST API Summary (`/api/v1/projects`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/projects` | Create a new project specification |
| `GET` | `/api/v1/projects` | List public projects or user's projects (`?my_projects=true`) |
| `GET` | `/api/v1/projects/{id}` | Retrieve complete project metadata, assets, and workers |
| `PATCH` | `/api/v1/projects/{id}` | Update project description or target workers |
| `POST` | `/api/v1/projects/{id}/online` | Put project online; verify assets and generate 9-digit code |
| `POST` | `/api/v1/projects/{id}/pause` | Pause training across cluster |
| `POST` | `/api/v1/projects/{id}/resume` | Resume paused training |
| `POST` | `/api/v1/projects/{id}/stop` | Stop training and release allocations |
| `POST` | `/api/v1/projects/{id}/end` | Conclude project and revoke join codes |
| `POST` | `/api/v1/projects/join-by-code` | Join a project using 9-digit numeric code |
| `GET` | `/api/v1/projects/{id}/membership` | Query worker membership status |
| `PATCH` | `/api/v1/projects/{id}/membership/resources` | Adjust worker compute budget for project |
| `POST` | `/api/v1/projects/{id}/leave` | Voluntarily leave project without halting cluster |
| `POST` | `/api/v1/projects/{id}/datasets` | Stream upload dataset with SHA-256 verification |
| `GET` | `/api/v1/projects/{id}/datasets` | List uploaded datasets for project |
| `GET` | `/api/v1/projects/{id}/datasets/{id}/download` | Stream download dataset package |
| `POST` | `/api/v1/projects/{id}/packages` | Stream upload training code (.zip/.tar.gz) & inspect manifest |
| `GET` | `/api/v1/projects/{id}/packages` | List uploaded model packages |
| `GET` | `/api/v1/projects/{id}/packages/{id}/download` | Stream download model package |
| `GET` | `/api/v1/projects/{id}/progress` | Retrieve current training metrics and step progress |
| `GET` | `/api/v1/projects/{id}/workers` | List connected worker nodes and contributed capacities |
