"""
Training Package Manifest specifications, parsing, and hardware compatibility validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import ValidationError


class ResourceRequirements(BaseModel):
    """Resource hardware bounds declared in package manifest."""
    model_config = ConfigDict(populate_by_name=True)

    min_cpu_cores: int = Field(1, ge=1, alias="minCpuCores")
    min_ram_gb: float = Field(2.0, ge=0.5, alias="minRamGB")
    min_vram_gb: float = Field(0.0, ge=0.0, alias="minVramGB")
    gpu_required: bool = Field(False, alias="gpuRequired")


class InputsConfig(BaseModel):
    """Declared dataset expectations for training code package."""
    model_config = ConfigDict(populate_by_name=True)

    dataset_type: str = Field("archive", alias="datasetType")
    dataset_path: str = Field("dataset", alias="datasetPath")


class OutputsConfig(BaseModel):
    """Output directory declarations for model checkpoints and execution logs."""
    model_config = ConfigDict(populate_by_name=True)

    checkpoints_dir: str = Field("checkpoints", alias="checkpointsDir")
    logs_dir: str = Field("logs", alias="logsDir")


class PackageManifest(BaseModel):
    """
    Standardized Training Package Manifest (Section 13).
    Describes package entry point, dependencies, requirements, and adapter.
    """
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field("training_package")
    version: str = Field("1.0.0")
    entrypoint: str = Field("train.py")
    dependencies: List[str] = Field(default_factory=list)
    required_resources: ResourceRequirements = Field(
        default_factory=ResourceRequirements,
        alias="requiredResources",
    )
    inputs: InputsConfig = Field(default_factory=InputsConfig)
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)
    supported_strategies: List[str] = Field(
        default_factory=lambda: ["single_node", "independent_jobs"],
        alias="supportedStrategies",
    )
    adapter: str = Field("adc_standard")
    python_version: Optional[str] = Field(None, alias="pythonVersion")


def validate_manifest_dict(data: Dict[str, Any]) -> PackageManifest:
    """Parse and validate manifest dictionary."""
    try:
        return PackageManifest.model_validate(data)
    except Exception as exc:
        raise ValidationError(f"Invalid package manifest: {exc}")


def parse_manifest_file(file_path: Path | str) -> PackageManifest:
    """Load, parse, and validate manifest.json file from path."""
    path = Path(file_path)
    if not path.is_file():
        raise ValidationError(f"Manifest file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Corrupt manifest.json: {exc}")

    return validate_manifest_dict(data)


def evaluate_machine_compatibility(
    manifest: PackageManifest,
    hardware: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Evaluate whether volunteer worker hardware satisfies package requirements.
    """
    reqs = manifest.required_resources

    # CPU validation
    cpu_cores = hardware.get("cpu", {}).get("logicalCores", 0)
    if cpu_cores < reqs.min_cpu_cores:
        return False, f"Machine logical CPU cores ({cpu_cores}) below required minimum ({reqs.min_cpu_cores})."

    # RAM validation
    ram_gb = hardware.get("memory", {}).get("totalGb", 0.0)
    if ram_gb < reqs.min_ram_gb:
        return False, f"Machine physical RAM ({ram_gb:.1f} GB) below required minimum ({reqs.min_ram_gb:.1f} GB)."

    # GPU validation
    gpus = hardware.get("gpus", [])
    if reqs.gpu_required and not gpus:
        return False, "Package requires dedicated GPU acceleration, but no GPU was detected."

    if reqs.min_vram_gb > 0:
        total_vram = sum(g.get("totalMemoryGb", 0.0) for g in gpus)
        if total_vram < reqs.min_vram_gb:
            return (
                False,
                f"Machine VRAM ({total_vram:.1f} GB) below required minimum ({reqs.min_vram_gb:.1f} GB).",
            )

    return True, None
