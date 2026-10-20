"""
Local Resource Guard and Safety Monitor.

Enforces:
- Local resource budget limits (CPU cores, RAM budget)
- Global pause state enforcement
- Host safety margin checks (preventing host OS freezing / OOM)
- Storage exhaustion prevention
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import psutil

from agents.common.hardware import HardwareDetector
from app.core.logging import get_logger

logger = get_logger("adc.resource_guard")


class ResourceGuard:
    """Monitors and enforces local resource budgets and host safety."""

    def __init__(
        self,
        cpu_cores_budget: int = 2,
        ram_budget_gb: float = 4.0,
        storage_budget_gb: float = 20.0,
        gpu_enabled: bool = False,
        selected_gpu: str = "",
        min_host_free_ram_gb: float = 0.5,
        min_host_free_disk_gb: float = 1.0,
        global_paused: bool = False,
    ) -> None:
        self.cpu_cores_budget = cpu_cores_budget
        self.ram_budget_gb = ram_budget_gb
        self.storage_budget_gb = storage_budget_gb
        self.gpu_enabled = gpu_enabled
        self.selected_gpu = selected_gpu
        self.min_host_free_ram_gb = min_host_free_ram_gb
        self.min_host_free_disk_gb = min_host_free_disk_gb
        self.global_paused = global_paused

    def update_settings(self, settings_dict: Dict[str, Any]) -> None:
        """Update guard configuration from backend contribution settings."""
        if "cpuCores" in settings_dict:
            self.cpu_cores_budget = int(settings_dict["cpuCores"])
        elif "cpu_cores" in settings_dict:
            self.cpu_cores_budget = int(settings_dict["cpu_cores"])

        if "ramBudgetGB" in settings_dict:
            self.ram_budget_gb = float(settings_dict["ramBudgetGB"])
        elif "ram_budget_gb" in settings_dict:
            self.ram_budget_gb = float(settings_dict["ram_budget_gb"])

        if "storageBudgetGB" in settings_dict:
            self.storage_budget_gb = float(settings_dict["storageBudgetGB"])
        elif "storage_budget_gb" in settings_dict:
            self.storage_budget_gb = float(settings_dict["storage_budget_gb"])

        if "gpuEnabled" in settings_dict:
            self.gpu_enabled = bool(settings_dict["gpuEnabled"])
        elif "gpu_enabled" in settings_dict:
            self.gpu_enabled = bool(settings_dict["gpu_enabled"])

        if "selectedGpu" in settings_dict:
            self.selected_gpu = str(settings_dict["selectedGpu"])
        elif "selected_gpu" in settings_dict:
            self.selected_gpu = str(settings_dict["selected_gpu"])

        if "globalPaused" in settings_dict:
            self.global_paused = bool(settings_dict["globalPaused"])
        elif "global_paused" in settings_dict:
            self.global_paused = bool(settings_dict["global_paused"])

    def check_safety(self) -> Tuple[bool, Optional[str]]:
        """
        Verify that it is safe to execute training compute right now.
        
        Returns (is_safe, failure_reason).
        """
        # 1. Global pause toggle
        if self.global_paused:
            return False, "Global contribution paused by user."

        # 2. Host RAM safety margin check
        ram = HardwareDetector.get_ram_info()
        if ram["available_gb"] < self.min_host_free_ram_gb:
            logger.warning(
                "host_memory_pressure_detected",
                available_gb=ram["available_gb"],
                threshold_gb=self.min_host_free_ram_gb,
            )
            return False, f"Host memory pressure: only {ram['available_gb']} GB available (safety threshold: {self.min_host_free_ram_gb} GB)."

        # 3. Disk storage check
        disk = HardwareDetector.get_disk_info()
        if disk["free_gb"] < self.min_host_free_disk_gb:
            logger.warning(
                "host_disk_pressure_detected",
                free_gb=disk["free_gb"],
                threshold_gb=self.min_host_free_disk_gb,
            )
            return False, f"Host disk space critically low: only {disk['free_gb']} GB free."

        return True, None

    def check_process_resource_usage(self, pid: int) -> Tuple[bool, Optional[str]]:
        """
        Check whether a running worker child process exceeds its allocated RAM budget.
        """
        try:
            proc = psutil.Process(pid)
            mem_bytes = proc.memory_info().rss
            mem_gb = mem_bytes / (1024**3)
            if mem_gb > self.ram_budget_gb:
                return False, f"Process exceeded allocated RAM budget: {mem_gb:.2f} GB used > {self.ram_budget_gb} GB limit."
            return True, None
        except psutil.NoSuchProcess:
            return True, None
        except Exception as exc:
            logger.debug("check_process_resource_usage_error", error=str(exc))
            return True, None
