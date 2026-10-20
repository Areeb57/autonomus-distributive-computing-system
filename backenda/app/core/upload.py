"""
Streaming file upload handling, SHA-256 integrity hashing, and archive manifest inspection.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import UploadFile

from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger("adc.upload")


async def save_upload_stream(
    upload_file: UploadFile,
    destination_path: Path,
    max_bytes: int = 10 * 1024 * 1024 * 1024,  # 10 GB default
    chunk_size: int = 1024 * 1024,  # 1 MB chunk
) -> Tuple[int, str]:
    """
    Stream upload directly to disk while computing SHA-256 hash on the fly.
    Enforces maximum size limit without loading the file into memory.
    """
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination_path.parent / f"{destination_path.name}.{uuid.uuid4().hex}.tmp"

    hasher = hashlib.sha256()
    total_bytes = 0

    try:
        with open(temp_path, "wb") as f:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise ValidationError(
                        f"Uploaded file exceeds maximum permitted size of {max_bytes / (1024 * 1024):.1f} MB."
                    )
                hasher.update(chunk)
                f.write(chunk)

        # Atomically replace final file
        if temp_path.exists():
            if destination_path.exists():
                destination_path.unlink()
            temp_path.rename(destination_path)

        checksum = hasher.hexdigest()
        logger.info(
            "file_upload_stream_completed",
            destination=str(destination_path),
            size_bytes=total_bytes,
            checksum=checksum,
        )
        return total_bytes, checksum

    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        logger.error("file_upload_stream_failed", error=str(exc))
        raise exc


def inspect_and_validate_package(
    package_path: Path,
    expected_entrypoint: str = "train.py",
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Safely inspect an uploaded model training package archive (.zip or .tar.gz).
    
    Verifies:
    1. No directory traversal / ZipSlip exploits (no '..' or leading '/').
    2. Existence of the expected execution entrypoint (e.g. train.py).
    3. Parses and extracts manifest.json if present.
    """
    if not package_path.exists():
        return False, "Package file does not exist.", None

    filename = package_path.name.lower()
    manifest_data: Optional[Dict[str, Any]] = None
    names: list[str] = []

    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(package_path, "r") as zf:
                names = zf.namelist()
                for name in names:
                    # Guard against path traversal / ZipSlip
                    if ".." in name or name.startswith("/") or name.startswith("\\"):
                        return False, f"Malicious archive member path detected: {name}", None

                # Look for manifest.json
                for name in names:
                    base = os.path.basename(name)
                    if base == "manifest.json":
                        try:
                            raw = zf.read(name)
                            manifest_data = json.loads(raw.decode("utf-8"))
                        except Exception as e:
                            return False, f"Invalid manifest.json in archive: {e}", None

        elif filename.endswith((".tar.gz", ".tgz", ".tar")):
            mode = "r:gz" if filename.endswith((".tar.gz", ".tgz")) else "r:"
            with tarfile.open(package_path, mode) as tf:
                names = tf.getnames()
                for name in names:
                    if ".." in name or name.startswith("/") or name.startswith("\\"):
                        return False, f"Malicious archive member path detected: {name}", None

                for member in tf.getmembers():
                    base = os.path.basename(member.name)
                    if base == "manifest.json" and member.isfile():
                        try:
                            f = tf.extractfile(member)
                            if f:
                                manifest_data = json.loads(f.read().decode("utf-8"))
                        except Exception as e:
                            return False, f"Invalid manifest.json in archive: {e}", None
        else:
            return False, "Unsupported package format. Allowed formats: .zip, .tar.gz, .tgz, .tar", None

        # Verify entrypoint existence
        basenames = [os.path.basename(n) for n in names]
        if expected_entrypoint not in basenames:
            return (
                False,
                f"Required entrypoint script '{expected_entrypoint}' was not found in the uploaded package.",
                None,
            )

        return True, None, manifest_data

    except Exception as exc:
        return False, f"Archive inspection failed: {exc}", None


def validate_dataset_archive(dataset_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that an uploaded dataset file is accessible and non-corrupt.
    """
    if not dataset_path.exists():
        return False, "Dataset file not found on disk."

    size = dataset_path.stat().st_size
    if size == 0:
        return False, "Dataset file is empty (0 bytes)."

    filename = dataset_path.name.lower()
    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(dataset_path, "r") as zf:
                bad_file = zf.testzip()
                if bad_file:
                    return False, f"Corrupted file in zip archive: {bad_file}"
        elif filename.endswith((".tar.gz", ".tgz", ".tar")):
            mode = "r:gz" if filename.endswith((".tar.gz", ".tgz")) else "r:"
            with tarfile.open(dataset_path, mode) as tf:
                # Check member count
                members = tf.getmembers()
                if not members:
                    return False, "Tar archive is empty."
        return True, None
    except Exception as exc:
        return False, f"Dataset archive integrity check failed: {exc}"
