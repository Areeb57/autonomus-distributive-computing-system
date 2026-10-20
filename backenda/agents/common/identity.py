"""
Persistent machine identity for ADC agent processes.

Manages:
- Installation ID persistence
- Ed25519 private/public keypair storage in local secure config file
- Challenge signing
"""

from __future__ import annotations

import json
import os
import platform
import socket
from pathlib import Path
from typing import Optional

from app.core.machine_crypto import (
    export_private_key_pem,
    generate_installation_id,
    generate_machine_keypair,
    load_private_key_pem,
    sign_message,
)


class MachineIdentity:
    """Encapsulates local machine installation credentials."""

    def __init__(
        self,
        installation_id: str,
        name: str,
        private_key_pem: str,
        public_key_hex: str,
        platform_name: str,
        storage_path: Path,
    ) -> None:
        self.installation_id = installation_id
        self.name = name
        self._private_key_pem = private_key_pem
        self.public_key_hex = public_key_hex
        self.platform_name = platform_name
        self.storage_path = storage_path
        self._private_key = load_private_key_pem(private_key_pem)

    def sign_challenge(self, message: bytes) -> str:
        """Sign a challenge message with the local private key."""
        return sign_message(self._private_key, message)

    def sign_timestamped_nonce(self, timestamp: int) -> str:
        """Sign '{installation_id}:{timestamp}' for authentication."""
        msg = f"{self.installation_id}:{timestamp}".encode("utf-8")
        return self.sign_challenge(msg)

    @classmethod
    def get_default_identity_path() -> Path:
        """Return the default configuration path for machine identity."""
        custom_path = os.environ.get("ADC_IDENTITY_FILE")
        if custom_path:
            return Path(custom_path)
        base = Path.home() / ".adc"
        base.mkdir(parents=True, exist_ok=True)
        return base / "machine_identity.json"

    @classmethod
    def load_or_create(cls, path: Optional[Path] = None, machine_name: Optional[str] = None) -> "MachineIdentity":
        """
        Load an existing machine identity from disk, or generate and persist a new one.
        """
        identity_path = path or cls.get_default_identity_path()

        if identity_path.exists():
            try:
                with open(identity_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(
                    installation_id=data["installation_id"],
                    name=data.get("name", machine_name or socket.gethostname()),
                    private_key_pem=data["private_key_pem"],
                    public_key_hex=data["public_key_hex"],
                    platform_name=data.get("platform", platform.system().lower()),
                    storage_path=identity_path,
                )
            except Exception:
                # If corrupted, regenerate
                pass

        # Generate new identity
        inst_id = generate_installation_id()
        name = machine_name or socket.gethostname() or "adc-node"
        priv_key, pub_hex = generate_machine_keypair()
        pem_str = export_private_key_pem(priv_key)
        plat = platform.system().lower()

        data = {
            "installation_id": inst_id,
            "name": name,
            "private_key_pem": pem_str,
            "public_key_hex": pub_hex,
            "platform": plat,
        }

        identity_path.parent.mkdir(parents=True, exist_ok=True)
        with open(identity_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return cls(
            installation_id=inst_id,
            name=name,
            private_key_pem=pem_str,
            public_key_hex=pub_hex,
            platform_name=plat,
            storage_path=identity_path,
        )
