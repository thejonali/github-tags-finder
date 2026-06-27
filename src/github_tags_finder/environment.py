"""Load GitHub-specific settings from a local environment file."""

from __future__ import annotations

import os
import re
from pathlib import Path


GITHUB_ENVIRONMENT_VARIABLES = frozenset({"GITHUB_TOKEN", "GH_TOKEN", "GITHUB_API_URL"})
_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_github_environment(path: str | Path = ".env") -> bool:
    """Load recognized GitHub variables without replacing existing values."""
    env_path = Path(path)
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return False

    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"Invalid environment entry at {env_path}:{number}")

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not _ENVIRONMENT_NAME.fullmatch(name):
            raise ValueError(f"Invalid environment variable at {env_path}:{number}")
        if name not in GITHUB_ENVIRONMENT_VARIABLES:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(name, value)
    return True
