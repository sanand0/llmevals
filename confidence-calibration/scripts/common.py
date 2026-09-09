"""Shared project paths and lazy OpenAI credential loading."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD = ROOT / ".build"
SRC = ROOT / "src"


def ensure_build() -> Path:
    BUILD.mkdir(exist_ok=True)
    return BUILD


def openai_api_key() -> str:
    """Return an OpenAI key only when an API call is actually required."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        proc = subprocess.run(
            ["llm", "keys", "get", "openai"],
            check=True,
            capture_output=True,
            text=True,
        )
        key = proc.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        key = ""
    if not key:
        raise RuntimeError(
            "Missing OpenAI API key. Set OPENAI_API_KEY or configure `llm keys set openai`."
        )
    return key
