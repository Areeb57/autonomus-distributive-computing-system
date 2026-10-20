# Hardware Detection, Resource Guard, and Telemetry

This document details the architecture, hardware introspection mechanics, resource budgeting, and safety guard enforcement for **ADC (Autonomous Distributed AI Trainer)** nodes.

---

## 1. Cross-Platform Hardware Detection Engine

Hardware detection is implemented in [`agents/common/hardware.py`](file:///d:/project/adc/backenda/agents/common/hardware.py) via `HardwareDetector`. It probes the host operating system directly without relying on external third-party binaries or mock values.

### A. CPU Model & Core Introspection
- **Windows**: Queries the Windows Registry at `HKEY_LOCAL_MACHINE\HARDWARE\DESCRIPTION\System\CentralProcessor\0\ProcessorNameString` to retrieve exact branded nomenclature (e.g. `Intel(R) Core(TM) i5-13400` or `AMD Ryzen 9 7950X`).
- **Linux**: Parses `model name` lines from `/proc/cpuinfo`.
- **macOS**: Queries the Darwin kernel via `sysctl -n machdep.cpu.brand_string`.
- **Cores & Utilization**: Uses `psutil.cpu_count(logical=True)` for schedulable compute threads and `logical=False` for physical execution cores. Utilization is captured via non-blocking sampling.

### B. RAM & Storage Capacity
- **Memory**: Probes `psutil.virtual_memory()`, recording `total`, `available`, `used`, and percentage utilization converted to gigabytes ($2^{30}$ bytes).
- **Disk Storage**: Probes target working directory storage via `psutil.disk_usage()`, recording total capacity, current free bytes, and utilization.

### C. GPU & VRAM Detection with Graceful CPU-Only Fallback
- First attempts to probe hardware using `torch.cuda` if PyTorch with CUDA support is installed. It enumerates device indices, model strings (`torch.cuda.get_device_name`), total VRAM, and dynamic free VRAM (`torch.cuda.mem_get_info`).
- If PyTorch CUDA is not present, it attempts to locate `nvidia-smi` on the system PATH and queries total and free memory.
- **CPU-Only Graceful Fallback**: If no GPU is installed or detected, `detect_gpus()` returns:
  ```json
  {
    "has_gpu": false,
    "gpu_count": 0,
    "primary_model": "None",
    "total_vram_gb": 0.0,
    "free_vram_gb": 0.0,
    "devices": []
  }
  ```
  The agent and platform run without crashing, treating the node as a CPU compute contributor.

---

## 2. Resource Guard and Local Safety Monitor

The `ResourceGuard` in [`agents/common/guard.py`](file:///d:/project/adc/backenda/agents/common/guard.py) runs locally within the Worker Agent. It enforces user-configured policies and prevents volunteer compute from degrading or freezing the host workstation.

### Operational Safety Thresholds
1. **Host RAM Safety Threshold (`min_host_free_ram_gb`)**:
   - Guard default: `0.5 GB` minimum headroom.
   - If total available host memory falls below this safety margin, the guard detects memory pressure and immediately flags unsafe status, preventing new tasks from spawning and triggering cooperative throttling to prevent OS out-of-memory kernel panics.
2. **Storage Starvation Safety (`min_host_free_disk_gb`)**:
   - Guard default: `1.0 GB` minimum free space.
   - Blocks dataset staging or checkpoint persistence if free disk falls below the safety boundary.
3. **Child Process Resident Memory Monitoring (`check_process_resource_usage`)**:
   - Probes child worker PID resident set size (`rss`).
   - If an active training process exceeds the user-configured `ram_budget_gb`, the guard flags budget violation.

### Enforceable Limits vs. Best-Effort Scheduling Targets
Per engineering requirements, we clearly differentiate what is strictly enforceable at the OS level versus what constitutes a scheduling allocation target:

| Resource Dimension | Enforcement Mechanism | Classification |
|---|---|---|
| **CPU Cores Allocation** | PyTorch `torch.set_num_threads()` / Process CPU affinity | **Strictly Enforceable** |
| **Worker Process RAM Limit** | Local `ResourceGuard` RSS monitor & cooperative threshold check | **Strictly Enforceable** |
| **Storage Quota (GB)** | Local disk usage check and pre-allocation validation | **Strictly Enforceable** |
| **Global Pause** | Immediate task suspension & rejection of new batch dispatches | **Strictly Enforceable** |
| **GPU Utilization Slider (%)** | Dynamic sleep interval between forward/backward passes | **Best-Effort Scheduling** |
| **GPU VRAM Allocation** | PyTorch `torch.cuda.set_per_process_memory_fraction` | **Enforceable on CUDA** |
| **Network Saver Mode** | Chunked upload rate limiting & deferred checkpoint syncing | **Scheduling Target** |

---

## 3. Database Schema: `machine_contribution_settings`

Persisted in PostgreSQL/SQLite and mapped in [`app/models/resource.py`](file:///d:/project/adc/backenda/app/models/resource.py):

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | Primary Key | Unique settings identifier |
| `machine_id` | UUID | Foreign Key (`machines.id`), Unique, NOT NULL | Linked compute machine |
| `user_id` | UUID | Foreign Key (`users.id`), NOT NULL | Owner user account |
| `cpu_enabled` | Boolean | NOT NULL, Default: `true` | Whether CPU compute is contributed |
| `cpu_cores` | Integer | NOT NULL, Default: `2` | Number of logical cores contributed |
| `ram_budget_gb` | Float | NOT NULL, Default: `4.0` | Maximum RAM allocated for compute |
| `gpu_enabled` | Boolean | NOT NULL, Default: `false` | Whether GPU compute is contributed |
| `selected_gpu` | String(128) | NOT NULL, Default: `""` | Selected GPU identifier |
| `storage_budget_gb` | Float | NOT NULL, Default: `20.0` | Maximum disk storage for datasets/models |
| `network_preference` | String(32) | NOT NULL, Default: `"unlimited"` | Network policy: `unlimited`, `moderate`, `saver` |
| `global_paused` | Boolean | NOT NULL, Default: `false` | Global contribution pause toggle |
| `created_at` | DateTime | NOT NULL, `now()` | Record creation timestamp |
| `updated_at` | DateTime | NOT NULL, `now()` | Last modification timestamp |

---

## 4. REST API Specification

Mounted under `/api/v1/resources` in [`app/api/routes/resources.py`](file:///d:/project/adc/backenda/app/api/routes/resources.py):

### 1. `GET /api/v1/resources/me`
Retrieves consolidated hardware capabilities, current contribution budgets, detected GPUs, and cluster aggregate capacity.
- **Headers**:
  - `Authorization: Bearer <token>` or session cookie
  - `X-Installation-Id: <id>` (optional; targets specific machine)
- **Response `200 OK`**:
  ```json
  {
    "hardwareProfile": {
      "cpuModel": "13th Gen Intel(R) Core(TM) i5-13400",
      "cpuCores": 16,
      "ramTotalGB": 31.78,
      "ramAvailableGB": 17.42,
      "gpuModel": "None",
      "gpuMemoryTotalGB": 0.0,
      "diskSpaceAvailableGB": 184.25
    },
    "contributionSettings": {
      "cpuEnabled": true,
      "cpuCores": 2,
      "ramBudgetGB": 4.0,
      "gpuEnabled": false,
      "selectedGpu": "",
      "storageBudgetGB": 20.0,
      "networkPreference": "unlimited",
      "globalPaused": false
    },
    "availableGpus": [],
    "clusterSummary": {
      "activeWorkersCount": 1,
      "totalContributedCpuCores": 2,
      "totalContributedRamGB": 4.0,
      "totalContributedStorageGB": 20.0
    }
  }
  ```

### 2. `PATCH /api/v1/resources/me`
Modifies contribution settings with physical capacity validation.
- **Body**:
  ```json
  {
    "cpuEnabled": true,
    "cpuCores": 4,
    "ramBudgetGB": 8.0,
    "storageBudgetGB": 40.0,
    "networkPreference": "moderate"
  }
  ```
- **Validation Rules**:
  - `cpuCores` cannot exceed host logical core count.
  - `ramBudgetGB` cannot exceed total physical RAM.
  - `storageBudgetGB` cannot exceed local disk capacity.
  - `gpuEnabled` cannot be enabled if `has_gpu` is false.
- **Response `200 OK`**: Returns updated `ContributionSettingsResponse`.
- **Response `422 Unprocessable Content`**: Returned if requested budget violates physical limits.

### 3. `POST /api/v1/resources/me/pause-all`
Activates global contribution pause across all projects for the authenticated user.
- **Response `200 OK`**:
  ```json
  {
    "globalPaused": true,
    "message": "All computing resource contributions have been paused across all projects.",
    "affectedMachines": 1
  }
  ```

### 4. `POST /api/v1/resources/me/resume-all`
Clears global pause flag and resumes compute availability.
- **Response `200 OK`**:
  ```json
  {
    "globalPaused": false,
    "message": "Computing resource contributions resumed.",
    "affectedMachines": 1
  }
  ```
