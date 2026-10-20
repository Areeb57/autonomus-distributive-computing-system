"""
Cryptographic machine identity primitives using Ed25519.

Provides:
- Machine installation ID generation
- Ed25519 keypair generation, export, import
- Nonce signing and signature verification for challenge-response auth
"""

from __future__ import annotations

import secrets
from typing import Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def generate_installation_id() -> str:
    """Generate a cryptographically random machine installation ID (e.g. inst_...)."""
    return f"inst_{secrets.token_hex(16)}"


def generate_machine_keypair() -> Tuple[ed25519.Ed25519PrivateKey, str]:
    """
    Generate an Ed25519 private key and return (private_key, public_key_hex).
    Public key is 32 bytes (64 hex characters).
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key, pub_bytes.hex()


def sign_message(private_key: ed25519.Ed25519PrivateKey, message: bytes) -> str:
    """Sign a message with an Ed25519 private key and return the signature as a hex string."""
    signature_bytes = private_key.sign(message)
    return signature_bytes.hex()


def verify_machine_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """
    Verify an Ed25519 signature against a public key hex and message bytes.
    Returns True if valid, False if invalid or malformed.
    """
    try:
        pub_bytes = bytes.fromhex(public_key_hex)
        sig_bytes = bytes.fromhex(signature_hex)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, message)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


def export_private_key_pem(private_key: ed25519.Ed25519PrivateKey) -> str:
    """Export private key to unencrypted PKCS8 PEM string."""
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem_bytes.decode("utf-8")


def load_private_key_pem(pem_str: str) -> ed25519.Ed25519PrivateKey:
    """Load an Ed25519 private key from a PEM string."""
    key = serialization.load_pem_private_key(
        pem_str.encode("utf-8"),
        password=None,
    )
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise ValueError("Key in PEM is not an Ed25519 private key")
    return key
