"""Allowlisted whisper.cpp model artifacts shared by fetch and transcription."""

from __future__ import annotations

import hashlib
from pathlib import Path

WHISPER_MODEL_REVISION = "5359861c739e955e79d9a303bcbc70fb988958b1"
WHISPER_MODEL_ARTIFACTS = {
    "base.en": "a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002",
    "large-v3-turbo": "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_model(name: str, directories: tuple[Path, ...]) -> Path | None:
    """Return only the exact allowlisted artifact after hashing its bytes."""
    expected = WHISPER_MODEL_ARTIFACTS.get(name)
    if expected is None:
        return None
    filename = f"ggml-{name}.bin"
    for directory in directories:
        candidate = directory / filename
        if candidate.is_file() and file_sha256(candidate) == expected:
            return candidate
    return None
