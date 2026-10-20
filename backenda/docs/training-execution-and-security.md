# Secure Training Package Execution, Sandboxing & Runtime Adapters (Phase 7)

## Overview

Uploaded Python training code is executable code and must be treated as untrusted. Per Section 13 and Section 14:
1. **Never execute untrusted code in the FastAPI server process.**
2. **Static AST Analysis:** All extracted scripts are analyzed before execution using `CodeSecurityScanner` to detect prohibited modules, dangerous OS execution calls, and sensitive host path access.
3. **Dedicated Process Sandboxing:** Each training task executes in an isolated filesystem workspace (`ExecutionSandbox`) with ZipSlip protection, read-only dataset access, and sanitized environment variables.
4. **Stable Training Adapter & Telemetry Pipeline:** Standardized JSON (`[ADC_METRIC]`) stdout parser and `ADCReporter` helper for model code.
5. **Process Tree Supervision & Resource Limits:** Real-time RAM and runtime quotas monitored via `psutil`, with cooperative SIGTERM shutdown followed by recursive tree-killing if unresponsive.
6. **Configurable Execution Backends:** `SubprocessTrainingExecutor` (default restricted local subprocess runner) and `DockerTrainingExecutor` (containerized isolation with capability drop and automatic fallback).

---

## 1. Package Manifest Specifications (`manifest.json`)

Every training package archive must contain a `manifest.json` describing its runtime expectations:

```json
{
  "name": "diffusion_lora_trainer",
  "version": "1.0.0",
  "entrypoint": "train.py",
  "dependencies": [
    "torch>=2.0.0",
    "diffusers>=0.25.0",
    "transformers",
    "numpy"
  ],
  "requiredResources": {
    "minCpuCores": 4,
    "minRamGB": 8.0,
    "minVramGB": 6.0,
    "gpuRequired": true
  },
  "inputs": {
    "datasetType": "archive",
    "datasetPath": "dataset"
  },
  "outputs": {
    "checkpointsDir": "checkpoints",
    "logsDir": "logs"
  },
  "supportedStrategies": [
    "single_node",
    "independent_jobs",
    "data_parallel"
  ],
  "adapter": "adc_standard"
}
```

### Machine Compatibility Evaluation

Before dispatching a task to a volunteer compute node, `evaluate_machine_compatibility` validates:
- Physical/logical CPU core count $\ge \text{minCpuCores}$.
- System physical RAM $\ge \text{minRamGB}$.
- GPU availability if $\text{gpuRequired} = \text{true}$.
- Dedicated VRAM $\ge \text{minVramGB}$.

---

## 2. Static Code Security Scanner (`CodeSecurityScanner`)

Before any Python script is launched in a sandbox, Python's Abstract Syntax Tree (`ast`) parses and verifies all `.py` files:

| Category | Prohibited Items | Action |
| :--- | :--- | :--- |
| **Banned Modules** | `ctypes`, `pty`, `code`, `codeop`, `commands`, `posix`, `nt` | Immediate rejection (`SecurityViolationError`) |
| **Banned OS Calls** | `os.system()`, `os.popen*()`, `os.spawn*()`, `os.exec*()` | Immediate rejection (`SecurityViolationError`) |
| **Dynamic Execution** | `eval()` or `exec()` on dynamic/obfuscated expressions | Immediate rejection (`SecurityViolationError`) |
| **Sensitive Host Tokens** | `/etc/shadow`, `/etc/passwd`, `C:\Windows\System32`, `.aws/credentials`, `id_rsa`, `docker.sock` | Immediate rejection (`SecurityViolationError`) |

Standard machine learning libraries (`torch`, `torch.nn`, `diffusers`, `torchvision`, `numpy`, `PIL`, `pathlib`, `os.path`, `os.environ`) are fully supported.

---

## 3. Sandboxing & Environment Sanitization (`ExecutionSandbox`)

Each training task receives an isolated directory tree:

```
storage/workspaces/<task_id>/
├── code/                   # Unpacked model package (read/execute)
│   ├── manifest.json
│   └── train.py
├── data/                   # Unpacked dataset (read-only)
│   └── images/
└── outputs/                # Model artifacts written here
    ├── checkpoints/        # Saved .pt / .safetensors files
    └── logs/               # execution.log
```

### Environment Sanitization

To prevent exfiltration of host secrets, all environment variables are filtered:
- **Stripped:** Any variable prefixed with or containing `AWS_`, `AZURE_`, `GOOGLE_`, `GITHUB_`, `DATABASE_`, `SECRET_`, `DOCKER_`, `TOKEN`, `API_KEY`.
- **Injected ADC Parameters:**
  - `ADC_TASK_ID`: Current task identifier
  - `ADC_STEP_START` / `ADC_STEP_END`: Assigned slice range
  - `ADC_TOTAL_STEPS`: Project total steps
  - `ADC_DATASET_DIR`: Absolute path to `data/`
  - `ADC_CHECKPOINT_DIR`: Absolute path to `outputs/checkpoints/`
  - `ADC_OUTPUT_DIR`: Absolute path to `outputs/`
  - `PYTHONUNBUFFERED`: `"1"`
  - `PYTHONPATH`: Clean path to `code/`

---

## 4. Stable Training Adapter (`TrainingAdapter` & `ADCReporter`)

User training code communicates real progress through `ADCReporter`:

```python
import os
import torch
from agents.executor.adapter import ADCReporter

reporter = ADCReporter()

# Inside training loop:
for step in range(step_start, step_end):
    # ... compute loss ...
    loss_val = float(loss.item())
    
    reporter.report_step(
        step=step + 1,
        loss=loss_val,
        learning_rate=0.0001,
        speed=18.5,
    )

# Save checkpoint:
ckpt_path = os.path.join(os.environ["ADC_CHECKPOINT_DIR"], f"ckpt_step_{step_end}.pt")
torch.save(model.state_dict(), ckpt_path)
reporter.report_checkpoint(ckpt_path, step=step_end)
```

The executor asynchronously captures child process stdout and parses lines matching `[ADC_METRIC] {json}` or standard regex expressions (`Step X/Y - loss: ...`), forwarding them to the backend API without blocking training.

---

## 5. Subprocess Supervision & Process Tree Cleanup

`SubprocessTrainingExecutor` supervises the child process:
- **Memory Quota:** Monitored via `psutil.Process(pid).memory_info().rss`. If the process tree exceeds `max_ram_gb`, the run is terminated with `ResourceLimitExceededError`.
- **Execution Timeout:** If elapsed runtime exceeds `max_runtime_seconds`, execution is aborted.
- **Tree Termination:** On cancellation or quota violation:
  1. Sends `proc.terminate()` for cooperative graceful shutdown.
  2. Waits 3 seconds for in-flight checkpoints to finalize.
  3. Recursively kills all descendant child processes (`psutil.Process.children(recursive=True)`) to eliminate orphan training processes.
