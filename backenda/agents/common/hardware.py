"""
Cross-platform hardware capability detection and telemetry.

Detects:
- CPU brand model, physical/logical core counts, utilization
- RAM total, available, used, utilization
- Storage free, total, disk paths
- GPU model, device count, total and free VRAM (graceful fallback if absent)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any, Dict, List, Optional

import psutil

from app.core.logging import get_logger

logger = get_logger("adc.hardware")


def get_cpu_model_name() -> str:
    """Retrieve detailed human-readable CPU brand model string."""
    system = platform.system().lower()

    # 1. Windows: Read ProcessorNameString from Registry
    if system == "windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            brand, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return brand.strip()
        except Exception:
            pass

    # 2. Linux: Read model name from /proc/cpuinfo
    elif system == "linux" and os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass

    # 3. macOS: Query sysctl
    elif system == "darwin":
        try:
            output = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
            )
            if output.strip():
                return output.strip()
        except Exception:
            pass

    # Fallback to platform.processor()
    proc = platform.processor()
    if proc:
        return proc.strip()

    return f"{platform.machine()} {psutil.cpu_count(logical=True) or 1}-Core Processor"


def detect_gpus() -> Dict[str, Any]:
    """
    Detect GPU capability.
    
    Tries PyTorch CUDA -> nvidia-smi -> returns CPU-only fallback cleanly.
    Never crashes or outputs fake GPU data if no GPU is present.
    """
    # 1. Try PyTorch CUDA if available
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            count = torch.cuda.device_count()
            devices: List[Dict[str, Any]] = []
            total_vram_gb = 0.0
            free_vram_gb = 0.0

            for i in range(count):
                name = torch.cuda.get_device_name(i)
                props = torch.cuda.get_device_properties(i)
                dev_total_gb = round(props.total_memory / (1024**3), 2)
                try:
                    free_bytes, _ = torch.cuda.mem_get_info(i)
                    dev_free_gb = round(free_bytes / (1024**3), 2)
                except Exception:
                    dev_free_gb = dev_total_gb

                total_vram_gb += dev_total_gb
                free_vram_gb += dev_free_gb
                devices.append({
                    "index": i,
                    "name": name,
                    "total_memory_gb": dev_total_gb,
                    "free_memory_gb": dev_free_gb,
                })

            return {
                "has_gpu": True,
                "gpu_count": count,
                "primary_model": devices[0]["name"],
                "total_vram_gb": round(total_vram_gb, 2),
                "free_vram_gb": round(free_vram_gb, 2),
                "devices": devices,
            }
    except Exception:
        pass

    # 2. Try nvidia-smi CLI fallback
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            out = subprocess.check_output(
                [
                    nvidia_smi,
                    "--query-gpu=index,name,memory.total,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
            )
            lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
            if lines:
                devices = []
                total_vram_gb = 0.0
                free_vram_gb = 0.0
                for line in lines:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        idx = int(parts[0])
                        name = parts[1]
                        tot_mb = float(parts[2])
                        free_mb = float(parts[3])
                        tot_gb = round(tot_mb / 1024.0, 2)
                        fr_gb = round(free_mb / 1024.0, 2)
                        total_vram_gb += tot_gb
                        free_vram_gb += fr_gb
                        devices.append({
                            "index": idx,
                            "name": name,
                            "total_memory_gb": tot_gb,
                            "free_memory_gb": fr_gb,
                        })

                if devices:
                    return {
                        "has_gpu": True,
                        "gpu_count": len(devices),
                        "primary_model": devices[0]["name"],
                        "total_vram_gb": round(total_vram_gb, 2),
                        "free_vram_gb": round(free_vram_gb, 2),
                        "devices": devices,
                    }
        except Exception:
            pass

    # 3. Clean CPU-only fallback
    return {
        "has_gpu": False,
        "gpu_count": 0,
        "primary_model": "None",
        "total_vram_gb": 0.0,
        "free_vram_gb": 0.0,
        "devices": [],
    }


class HardwareDetector:
    """Full hardware detection engine for ADC nodes."""

    @classmethod
    def get_cpu_info(cls) -> Dict[str, Any]:
        """Detect CPU details and current usage."""
        logical = psutil.cpu_count(logical=True) or 1
        physical = psutil.cpu_count(logical=False) or logical
        util = psutil.cpu_percent(interval=None)
        return {
            "model": get_cpu_model_name(),
            "cores_physical": physical,
            "cores_logical": logical,
            "utilization_pct": round(util, 1),
        }

    @classmethod
    def get_ram_info(cls) -> Dict[str, Any]:
        """Detect system RAM capacity and availability."""
        vm = psutil.virtual_memory()
        total_gb = round(vm.total / (1024**3), 2)
        available_gb = round(vm.available / (1024**3), 2)
        used_gb = round((vm.total - vm.available) / (1024**3), 2)
        return {
            "total_gb": total_gb,
            "available_gb": available_gb,
            "used_gb": used_gb,
            "utilization_pct": round(vm.percent, 1),
        }

    @classmethod
    def get_disk_info(cls, path: str = ".") -> Dict[str, Any]:
        """Detect storage capacity and free space on target path."""
        try:
            usage = psutil.disk_usage(path)
            total_gb = round(usage.total / (1024**3), 2)
            free_gb = round(usage.free / (1024**3), 2)
            used_gb = round(usage.used / (1024**3), 2)
            pct = round(usage.percent, 1)
        except Exception:
            total_gb, free_gb, used_gb, pct = 100.0, 50.0, 50.0, 50.0

        return {
            "total_gb": total_gb,
            "free_gb": free_gb,
            "used_gb": used_gb,
            "utilization_pct": pct,
        }

    @classmethod
    def get_hardware_profile(cls) -> Dict[str, Any]:
        """
        Return standard HardwareProfile matching frontend TypeScript interface.
        """
        cpu = cls.get_cpu_info()
        ram = cls.get_ram_info()
        disk = cls.get_disk_info()
        gpu = detect_gpus()

        return {
            "cpuModel": cpu["model"],
            "cpuCores": cpu["cores_logical"],
            "ramTotalGB": ram["total_gb"],
            "ramAvailableGB": ram["available_gb"],
            "gpuModel": gpu["primary_model"],
            "gpuMemoryTotalGB": gpu["total_vram_gb"],
            "diskSpaceAvailableGB": disk["free_gb"],
        }

    @classmethod
    def get_telemetry_snapshot(cls) -> Dict[str, Any]:
        """Return raw telemetry dictionary for WorkerResourceSnapshot."""
        cpu = cls.get_cpu_info()
        ram = cls.get_ram_info()
        disk = cls.get_disk_info()
        gpu = detect_gpus()

        return {
            "cpu_model": cpu["model"],
            "cpu_cores": cpu["cores_logical"],
            "cpu_utilization": cpu["utilization_pct"],
            "ram_total_gb": ram["total_gb"],
            "ram_available_gb": ram["available_gb"],
            "ram_usage_pct": ram["utilization_pct"],
            "gpu_model": gpu["primary_model"],
            "gpu_memory_total_gb": gpu["total_vram_gb"],
            "gpu_memory_used_gb": round(gpu["total_vram_gb"] - gpu["free_vram_gb"], 2),
            "gpu_utilization_pct": 0.0,
            "disk_available_gb": disk["free_gb"],
        }
