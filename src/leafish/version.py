"""Version resolution and metadata for supported Minecraft versions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .exceptions import UnsupportedVersionError

_DATA_DIR = "leafish/data"
_VERSIONS_DIR = "versions"


@dataclass(frozen=True)
class VersionInfo:
    """Static information about one supported Minecraft version."""

    minecraft_version: str
    """Minecraft version string, e.g. ``"1.21.1"``."""

    protocol_version: int
    """Numeric protocol version sent in the handshake."""

    data_dir: Path | None = None
    """Filesystem path of the vendored minecraft-data directory, if any."""


def _versions_root() -> Path:
    """Return the directory containing vendored per-version data."""
    try:
        return Path(str(resources.files(_DATA_DIR) / _VERSIONS_DIR))
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        # Fallback for running from a source checkout.
        return Path(__file__).parent / "data" / "versions"


def list_versions() -> list[str]:
    """Return the Minecraft version strings for which data is vendored."""
    root = _versions_root()
    if not root.is_dir():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and (p / "version.json").exists()
    )


def load_version_json(version: str, name: str) -> Any:
    """Load ``<name>.json`` for a vendored Minecraft *version*."""
    path = _versions_root() / version / f"{name}.json"
    if not path.exists():
        raise UnsupportedVersionError(
            f"Minecraft {version} has no vendored '{name}' data"
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_version(requested: str) -> str:
    """Resolve ``requested`` (``"latest"`` or a version string) to a vendored version."""
    if requested != "latest":
        if requested not in list_versions():
            raise UnsupportedVersionError(
                f"Minecraft {requested} is not supported. "
                f"Available: {', '.join(list_versions()) or '(none)'}"
            )
        return requested
    versions = list_versions()
    if not versions:
        raise UnsupportedVersionError("No Minecraft version data is vendored")
    return versions[-1]


def get_version_info(version: str) -> VersionInfo:
    """Return protocol metadata for a vendored *version*."""
    resolved = resolve_version(version)
    vjson = load_version_json(resolved, "version")
    return VersionInfo(
        minecraft_version=resolved,
        protocol_version=int(vjson["version"]),
        data_dir=_versions_root() / resolved,
    )
