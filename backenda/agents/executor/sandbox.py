"""
Isolated execution sandbox manager for unprivileged training runs (Section 13).
"""

from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from agents.executor.manifest import PackageManifest, parse_manifest_file
from agents.executor.security import CodeSecurityScanner
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger("adc.executor.sandbox")

# Environment variable prefixes or tokens strictly stripped before passing to child process
SENSITIVE_ENV_PREFIXES = (
    "AWS_",
    "AZURE_",
    "GOOGLE_",
    "GITHUB_",
    "OPENAI_",
    "ANTHROPIC_",
    "DATABASE_",
    "SECRET_",
    "POSTGRES_",
    "DOCKER_",
    "SSH_",
    "TOKEN",
    "API_KEY",
)


class ExecutionSandbox:
    """
    Manages isolated filesystem workspace and sanitized runtime environment for a training task.
    """

    def __init__(
        self,
        task_id: str | uuid.UUID,
        base_dir: Optional[Path | str] = None,
    ) -> None:
        self.task_id = str(task_id)
        root_base = Path(base_dir) if base_dir else Path.cwd() / "storage" / "workspaces"
        self.sandbox_dir = root_base / self.task_id

        # Directory structure
        self.code_dir = self.sandbox_dir / "code"
        self.data_dir = self.sandbox_dir / "data"
        self.outputs_dir = self.sandbox_dir / "outputs"
        self.checkpoints_dir = self.outputs_dir / "checkpoints"
        self.logs_dir = self.outputs_dir / "logs"

    def setup_directories(self) -> None:
        """Create clean workspace directory hierarchy."""
        for d in (self.code_dir, self.data_dir, self.outputs_dir, self.checkpoints_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)
        logger.info("sandbox_directories_created", sandbox=str(self.sandbox_dir))

    def extract_package(self, package_zip_path: Path | str) -> PackageManifest:
        """
        Safely unpack model package zip file, validate against ZipSlip, and inspect manifest.
        """
        pkg_path = Path(package_zip_path)
        if not pkg_path.is_file():
            raise ValidationError(f"Package archive not found: {pkg_path}")

        real_target_dir = self.code_dir.resolve()
        with zipfile.ZipFile(pkg_path, "r") as zf:
            for member in zf.infolist():
                target_path = (real_target_dir / member.filename).resolve()
                if not str(target_path).startswith(str(real_target_dir)):
                    raise ValidationError(
                        f"ZipSlip security violation in package: '{member.filename}' escapes target directory."
                    )
            zf.extractall(self.code_dir)

        # 1. Verify manifest.json exists and parse it
        manifest_file = self.code_dir / "manifest.json"
        if not manifest_file.is_file():
            raise ValidationError("Missing required 'manifest.json' inside training package archive.")

        manifest = parse_manifest_file(manifest_file)

        # 2. Verify declared entrypoint exists
        entrypoint_file = self.code_dir / manifest.entrypoint
        if not entrypoint_file.is_file():
            raise ValidationError(f"Declared entrypoint '{manifest.entrypoint}' not found in package.")

        # 3. Perform static AST security scan on all extracted Python scripts
        CodeSecurityScanner.scan_package_directory(self.code_dir)

        return manifest

    def extract_dataset(self, dataset_zip_path: Path | str) -> None:
        """
        Safely unpack dataset zip archive into sandbox data directory.
        """
        ds_path = Path(dataset_zip_path)
        if not ds_path.is_file():
            raise ValidationError(f"Dataset archive not found: {ds_path}")

        real_target_dir = self.data_dir.resolve()
        with zipfile.ZipFile(ds_path, "r") as zf:
            for member in zf.infolist():
                target_path = (real_target_dir / member.filename).resolve()
                if not str(target_path).startswith(str(real_target_dir)):
                    raise ValidationError(
                        f"ZipSlip security violation in dataset: '{member.filename}' escapes target directory."
                    )
            zf.extractall(self.data_dir)

    def get_sanitized_environment(
        self,
        step_start: int = 0,
        step_end: int = 100,
        total_steps: int = 1000,
        resume_checkpoint_path: Optional[Path | str] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Generate sanitized process environment with host secrets stripped and ADC variables injected.
        """
        clean_env: Dict[str, str] = {}

        # Safe system variables to inherit
        safe_keys = {
            "PATH",
            "SYSTEMROOT",
            "COMSPEC",
            "TEMP",
            "TMP",
            "WINDIR",
            "HOME",
            "USER",
            "LANG",
            "LC_ALL",
            "CUDA_VISIBLE_DEVICES",
            "OMP_NUM_THREADS",
        }

        for k, v in os.environ.items():
            k_upper = k.upper()
            # Omit sensitive keys
            if any(k_upper.startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES):
                continue
            if k_upper in safe_keys:
                clean_env[k] = v

        # Injected ADC execution parameters
        clean_env["ADC_TASK_ID"] = self.task_id
        clean_env["ADC_STEP_START"] = str(step_start)
        clean_env["ADC_STEP_END"] = str(step_end)
        clean_env["ADC_TOTAL_STEPS"] = str(total_steps)
        clean_env["ADC_DATASET_DIR"] = str(self.data_dir.resolve())
        clean_env["ADC_OUTPUT_DIR"] = str(self.outputs_dir.resolve())
        clean_env["ADC_CHECKPOINT_DIR"] = str(self.checkpoints_dir.resolve())
        clean_env["PYTHONUNBUFFERED"] = "1"

        if resume_checkpoint_path:
            clean_env["ADC_RESUME_CHECKPOINT"] = str(Path(resume_checkpoint_path).resolve())

        # Prepend code_dir to PYTHONPATH so local modules resolve cleanly
        existing_pypath = clean_env.get("PYTHONPATH", "")
        code_str = str(self.code_dir.resolve())
        clean_env["PYTHONPATH"] = f"{code_str}{os.pathsep}{existing_pypath}" if existing_pypath else code_str

        if extra_env:
            clean_env.update(extra_env)

        return clean_env

    def cleanup(self, keep_outputs: bool = True) -> None:
        """
        Clean up temporary code and data directories after execution.
        """
        try:
            if self.code_dir.exists():
                shutil.rmtree(self.code_dir, ignore_errors=True)
            if self.data_dir.exists():
                shutil.rmtree(self.data_dir, ignore_errors=True)
            if not keep_outputs and self.outputs_dir.exists():
                shutil.rmtree(self.outputs_dir, ignore_errors=True)
            logger.info("sandbox_cleaned", task_id=self.task_id, keep_outputs=keep_outputs)
        except Exception as exc:
            logger.warning("sandbox_cleanup_error", task_id=self.task_id, error=str(exc))
