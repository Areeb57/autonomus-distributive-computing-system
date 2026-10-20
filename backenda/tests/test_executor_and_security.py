"""
Automated tests for Secure Training Package Execution, Sandboxing, Security Scanner, and Adapters (Phase 7).
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import List

import pytest
import torch
import torch.nn as nn

from agents.executor.adapter import ADCReporter, TrainingAdapter, TrainingTelemetry
from agents.executor.base import ExecutionResult, TaskExecutionConfig
from agents.executor.docker_executor import DockerTrainingExecutor
from agents.executor.manifest import (
    PackageManifest,
    ResourceRequirements,
    evaluate_machine_compatibility,
    parse_manifest_file,
    validate_manifest_dict,
)
from agents.executor.sandbox import ExecutionSandbox
from agents.executor.security import CodeSecurityScanner, SecurityViolationError
from agents.executor.subprocess_executor import SubprocessTrainingExecutor
from app.core.exceptions import ValidationError


# ── Helpers to generate packages & datasets ──────────────────────────────────


def create_safe_training_package(tmp_path: Path) -> Path:
    """Create a valid training package zip containing train.py and manifest.json."""
    pkg_zip = tmp_path / "valid_pkg.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Real PyTorch training code using ADCReporter
        code = """
import os
import torch
import torch.nn as nn
from agents.executor.adapter import ADCReporter

step_start = int(os.environ.get("ADC_STEP_START", "0"))
step_end = int(os.environ.get("ADC_STEP_END", "10"))
ckpt_dir = os.environ.get("ADC_CHECKPOINT_DIR", ".")

reporter = ADCReporter()

# Simple Linear model
model = nn.Linear(4, 1)
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
criterion = nn.MSELoss()

x = torch.randn(8, 4)
y = torch.randn(8, 1)

for step in range(step_start, step_end):
    optimizer.zero_grad()
    out = model(x)
    loss = criterion(out, y)
    loss.backward()
    optimizer.step()
    
    reporter.report_step(
        step=step + 1,
        loss=float(loss.item()),
        learning_rate=0.01,
        speed=25.0
    )

# Save real PyTorch checkpoint
ckpt_path = os.path.join(ckpt_dir, f"model_step_{step_end}.pt")
torch.save(model.state_dict(), ckpt_path)
reporter.report_checkpoint(ckpt_path, step=step_end)
print("Training execution finished successfully!")
"""
        zf.writestr("train.py", code)
        manifest = {
            "name": "diffusion_trainer",
            "version": "1.0.0",
            "entrypoint": "train.py",
            "dependencies": ["torch>=2.0.0", "numpy"],
            "requiredResources": {
                "minCpuCores": 1,
                "minRamGB": 1.0,
                "gpuRequired": False,
            },
            "supportedStrategies": ["single_node", "independent_jobs"],
            "adapter": "adc_standard",
        }
        zf.writestr("manifest.json", json.dumps(manifest))

    pkg_zip.write_bytes(buf.getvalue())
    return pkg_zip


def create_malicious_package(tmp_path: Path, bad_code: str) -> Path:
    """Create a package containing untrusted/malicious code."""
    pkg_zip = tmp_path / "malicious_pkg.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("train.py", bad_code)
        manifest = {
            "name": "bad_trainer",
            "version": "1.0.0",
            "entrypoint": "train.py",
        }
        zf.writestr("manifest.json", json.dumps(manifest))
    pkg_zip.write_bytes(buf.getvalue())
    return pkg_zip


def create_sample_dataset(tmp_path: Path) -> Path:
    """Create a sample dataset zip file."""
    ds_zip = tmp_path / "dataset.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("train.csv", "feature1,feature2,target\n1.0,2.0,3.0\n")
    ds_zip.write_bytes(buf.getvalue())
    return ds_zip


# ── 1. Manifest Parsing & Hardware Compatibility Tests ───────────────────────


def test_manifest_parsing_and_validation(tmp_path: Path):
    manifest_file = tmp_path / "manifest.json"
    manifest_data = {
        "name": "stable_diffusion_xl",
        "version": "2.1.0",
        "entrypoint": "train.py",
        "dependencies": ["torch", "diffusers>=0.25.0"],
        "requiredResources": {
            "minCpuCores": 4,
            "minRamGB": 16.0,
            "minVramGB": 8.0,
            "gpuRequired": True,
        },
        "supportedStrategies": ["single_node", "data_parallel"],
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    manifest = parse_manifest_file(manifest_file)
    assert manifest.name == "stable_diffusion_xl"
    assert manifest.version == "2.1.0"
    assert manifest.required_resources.min_cpu_cores == 4
    assert manifest.required_resources.min_ram_gb == 16.0
    assert manifest.required_resources.gpu_required is True

    # Rejection of invalid manifest (e.g. minCpuCores < 1)
    with pytest.raises(ValidationError):
        validate_manifest_dict({"requiredResources": {"minCpuCores": -2}})


def test_hardware_compatibility_evaluator():
    manifest = PackageManifest(
        required_resources=ResourceRequirements(
            min_cpu_cores=4,
            min_ram_gb=16.0,
            min_vram_gb=8.0,
            gpu_required=True,
        )
    )

    # 1. Matching hardware
    good_hw = {
        "cpu": {"logicalCores": 8},
        "memory": {"totalGb": 32.0},
        "gpus": [{"name": "RTX 4090", "totalMemoryGb": 24.0}],
    }
    ok, reason = evaluate_machine_compatibility(manifest, good_hw)
    assert ok is True
    assert reason is None

    # 2. Deficient CPU
    low_cpu = {"cpu": {"logicalCores": 2}, "memory": {"totalGb": 32.0}, "gpus": [{"totalMemoryGb": 24.0}]}
    ok, reason = evaluate_machine_compatibility(manifest, low_cpu)
    assert ok is False
    assert "cpu" in reason.lower()

    # 3. Deficient RAM
    low_ram = {"cpu": {"logicalCores": 8}, "memory": {"totalGb": 8.0}, "gpus": [{"totalMemoryGb": 24.0}]}
    ok, reason = evaluate_machine_compatibility(manifest, low_ram)
    assert ok is False
    assert "ram" in reason.lower()

    # 4. Missing GPU
    no_gpu = {"cpu": {"logicalCores": 8}, "memory": {"totalGb": 32.0}, "gpus": []}
    ok, reason = evaluate_machine_compatibility(manifest, no_gpu)
    assert ok is False
    assert "gpu" in reason.lower()


# ── 2. AST Code Security Scanner Tests ───────────────────────────────────────


def test_code_security_scanner_safe_code():
    safe_code = """
import os
from pathlib import Path
import torch
import numpy as np

model = torch.nn.Linear(10, 2)
data_dir = os.environ.get("ADC_DATASET_DIR")
print("All safe ML operations!")
"""
    violations = CodeSecurityScanner.scan_code_string(safe_code)
    assert len(violations) == 0


def test_code_security_scanner_detects_banned_modules():
    bad_code = """
import ctypes
import pty

print("attempting unsafe memory access")
"""
    violations = CodeSecurityScanner.scan_code_string(bad_code)
    assert len(violations) >= 2
    assert any("ctypes" in v for v in violations)
    assert any("pty" in v for v in violations)


def test_code_security_scanner_detects_dangerous_os_calls():
    bad_code = """
import os

os.system("rm -rf /")
os.popen("id")
"""
    violations = CodeSecurityScanner.scan_code_string(bad_code)
    assert len(violations) >= 2
    assert any("system()" in v for v in violations)
    assert any("popen()" in v for v in violations)


def test_code_security_scanner_detects_sensitive_host_paths():
    bad_code = """
with open("/etc/shadow", "r") as f:
    pass
with open("C:\\\\Windows\\\\System32\\\\cmd.exe", "rb") as f:
    pass
"""
    violations = CodeSecurityScanner.scan_code_string(bad_code)
    assert len(violations) >= 2
    assert any("shadow" in v for v in violations)
    assert any("System32" in v for v in violations)


def test_code_security_scanner_rejects_malicious_package(tmp_path: Path):
    bad_code = "import ctypes\nprint('evil')\n"
    pkg = create_malicious_package(tmp_path, bad_code)

    sandbox = ExecutionSandbox(task_id="test_malicious", base_dir=tmp_path / "ws")
    sandbox.setup_directories()

    with pytest.raises(SecurityViolationError) as exc_info:
        sandbox.extract_package(pkg)
    assert "ctypes" in str(exc_info.value)


# ── 3. Training Adapter & Telemetry Parser Tests ─────────────────────────────


def test_training_adapter_json_parsing():
    raw_line = '[ADC_METRIC] {"step": 42, "loss": 0.185, "speed": 16.4, "learningRate": 0.0005}'
    telemetry = TrainingAdapter.parse_stdout_line(raw_line)
    assert telemetry is not None
    assert telemetry.step == 42
    assert telemetry.loss == 0.185
    assert telemetry.speed == 16.4
    assert telemetry.learning_rate == 0.0005


def test_training_adapter_checkpoint_parsing():
    ckpt_line = "[ADC_CHECKPOINT] outputs/checkpoints/diffusion_model.pt"
    telemetry = TrainingAdapter.parse_stdout_line(ckpt_line)
    assert telemetry is not None
    assert telemetry.checkpoint_path == "outputs/checkpoints/diffusion_model.pt"


def test_training_adapter_regex_fallback():
    regex_line = "Epoch 1, Step: 75/200, loss: 0.298, lr: 0.0002, speed: 12.8 it/s"
    telemetry = TrainingAdapter.parse_stdout_line(regex_line)
    assert telemetry is not None
    assert telemetry.step == 75
    assert telemetry.total_steps == 200
    assert telemetry.loss == 0.298
    assert telemetry.learning_rate == 0.0002
    assert telemetry.speed == 12.8


def test_training_adapter_ignores_plain_logs():
    plain_line = "Loading checkpoint weights from disk into memory..."
    telemetry = TrainingAdapter.parse_stdout_line(plain_line)
    assert telemetry is None


# ── 4. Execution Sandbox Environment & Isolation Tests ───────────────────────


def test_execution_sandbox_environment_isolation(tmp_path: Path):
    sandbox = ExecutionSandbox(task_id="env_test", base_dir=tmp_path / "ws")
    sandbox.setup_directories()

    # Set mock host environment variables
    os.environ["AWS_SECRET_ACCESS_KEY"] = "super_secret_aws"
    os.environ["GITHUB_TOKEN"] = "secret_gh_token"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@host/db"
    os.environ["SAFE_INHERITED_VAR"] = "unrelated"

    clean_env = sandbox.get_sanitized_environment(
        step_start=10,
        step_end=50,
        total_steps=500,
    )

    # Host secrets must be completely absent
    assert "AWS_SECRET_ACCESS_KEY" not in clean_env
    assert "GITHUB_TOKEN" not in clean_env
    assert "DATABASE_URL" not in clean_env

    # ADC parameters must be injected
    assert clean_env["ADC_TASK_ID"] == "env_test"
    assert clean_env["ADC_STEP_START"] == "10"
    assert clean_env["ADC_STEP_END"] == "50"
    assert clean_env["ADC_TOTAL_STEPS"] == "500"
    assert "data" in clean_env["ADC_DATASET_DIR"]
    assert "checkpoints" in clean_env["ADC_CHECKPOINT_DIR"]
    assert clean_env["PYTHONUNBUFFERED"] == "1"


# ── 5. End-to-End Real PyTorch Execution in Subprocess Sandbox ───────────────


@pytest.mark.asyncio
async def test_subprocess_training_executor_real_execution(tmp_path: Path):
    """
    Executes a real training package using PyTorch in an isolated child process sandbox,
    verifying live metric parsing, checkpoint generation, log writing, and cleanup.
    """
    pkg_file = create_safe_training_package(tmp_path)
    ds_file = create_sample_dataset(tmp_path)

    reported_metrics: List[TrainingTelemetry] = []

    async def on_metric(metric: TrainingTelemetry) -> None:
        reported_metrics.append(metric)

    executor = SubprocessTrainingExecutor(sandbox_base_dir=tmp_path / "workspaces")
    config = TaskExecutionConfig(
        task_id="task_real_run",
        project_id="proj_diffusion_1",
        package_path=pkg_file,
        dataset_path=ds_file,
        step_start=0,
        step_end=5,
        total_steps=20,
    )

    result = await executor.execute(config, on_metric=on_metric)

    assert result.success is True
    assert result.exit_code == 0
    assert result.steps_completed == 5
    assert result.last_loss is not None
    assert len(result.checkpoints) >= 1
    assert any("model_step_5.pt" in ckpt for ckpt in result.checkpoints)
    assert result.log_file_path is not None
    assert Path(result.log_file_path).is_file()

    # Verify real metrics were emitted and captured in real-time
    step_metrics = [m for m in reported_metrics if m.loss is not None]
    assert len(step_metrics) >= 5
    assert step_metrics[-1].step == 5
    assert step_metrics[-1].loss is not None

    checkpoint_events = [m for m in reported_metrics if m.checkpoint_path is not None]
    assert len(checkpoint_events) >= 1
    assert "model_step_5.pt" in checkpoint_events[0].checkpoint_path

    # Verify created checkpoint is a valid PyTorch model weights file
    saved_weights = torch.load(result.checkpoints[0], weights_only=True)
    assert "weight" in saved_weights
    assert "bias" in saved_weights


# ── 6. Cooperative Cancellation & Timeout Supervision Tests ──────────────────


@pytest.mark.asyncio
async def test_subprocess_training_executor_timeout_enforcement(tmp_path: Path):
    """Verify that execution exceeding timeout is aborted."""
    infinite_code = """
import time
while True:
    time.sleep(0.5)
"""
    pkg = create_malicious_package(tmp_path, infinite_code)
    ds = create_sample_dataset(tmp_path)

    executor = SubprocessTrainingExecutor(sandbox_base_dir=tmp_path / "timeout_ws")
    config = TaskExecutionConfig(
        task_id="task_timeout",
        project_id="proj_test",
        package_path=pkg,
        dataset_path=ds,
        max_runtime_seconds=2,  # Short timeout for test
    )

    result = await executor.execute(config)
    assert result.success is False
    assert "exceeded" in str(result.error_message).lower() or result.exit_code != 0


# ── 7. Docker Training Executor Fallback Tests ────────────────────────────────


@pytest.mark.asyncio
async def test_docker_executor_fallback_behavior(tmp_path: Path):
    pkg_file = create_safe_training_package(tmp_path)
    ds_file = create_sample_dataset(tmp_path)

    # When Docker is unavailable, executor falls back to subprocess executor
    docker_executor = DockerTrainingExecutor(allow_fallback=True)
    docker_executor._subprocess_executor.sandbox_base_dir = tmp_path / "docker_ws"

    config = TaskExecutionConfig(
        task_id="task_docker_fallback",
        project_id="proj_test",
        package_path=pkg_file,
        dataset_path=ds_file,
        step_start=0,
        step_end=2,
    )

    result = await docker_executor.execute(config)
    assert result.success is True
    assert result.exit_code == 0
    assert result.steps_completed == 2
