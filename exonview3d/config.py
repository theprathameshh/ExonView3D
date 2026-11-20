"""Locations and environment-variable configuration."""

import os
import sys
from pathlib import Path

ENV_CACHE_DIR = "EXONVIEW3D_CACHE_DIR"
ENV_CA_BUNDLE = "EXONVIEW3D_CA_BUNDLE"


def default_cache_dir():
    """Per-user cache directory for downloaded AlphaFold files."""

    override = os.environ.get(ENV_CACHE_DIR)
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(base) / "exonview3d" / "cache"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "exonview3d"

    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "exonview3d"


def resolve_ca_bundle(explicit=None):
    """Return a CA bundle path from the argument or the environment."""

    value = explicit or os.environ.get(ENV_CA_BUNDLE)

    if not value:
        return None

    path = Path(value).expanduser()

    if not path.is_file():
        from .errors import InvalidInput

        raise InvalidInput(f"CA certificate bundle not found: {path}")

    return str(path)
