"""Ed25519 signing used for capability tokens, bundle manifests, chain anchors and
observer-daemon checkpoints. Private keys are held by exactly one process class each
(HLD §4.3): token key -> controller; bundle key -> offline (D14); chain key -> audit
sequencer; daemon key -> observer daemon.
"""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class Signer:
    def __init__(self, key: Ed25519PrivateKey):
        self._key = key

    @classmethod
    def generate(cls) -> "Signer":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def load(cls, path: str | os.PathLike) -> "Signer":
        raw = Path(path).read_bytes()
        return cls(serialization.load_pem_private_key(raw, password=None))  # type: ignore[arg-type]

    def save(self, path: str | os.PathLike) -> None:
        pem = self._key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o400)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)

    def sign(self, data: bytes) -> bytes:
        return self._key.sign(data)

    @property
    def verifier(self) -> "Verifier":
        return Verifier(self._key.public_key())


class Verifier:
    def __init__(self, key: Ed25519PublicKey):
        self._key = key

    @classmethod
    def load(cls, path: str | os.PathLike) -> "Verifier":
        return cls(serialization.load_pem_public_key(Path(path).read_bytes()))  # type: ignore[arg-type]

    @classmethod
    def from_pem(cls, pem: bytes) -> "Verifier":
        return cls(serialization.load_pem_public_key(pem))  # type: ignore[arg-type]

    def pem(self) -> bytes:
        return self._key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def save(self, path: str | os.PathLike) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.pem())

    def verify(self, sig: bytes, data: bytes) -> bool:
        try:
            self._key.verify(sig, data)
            return True
        except InvalidSignature:
            return False
