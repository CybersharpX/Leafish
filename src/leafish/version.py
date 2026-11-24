"""Version resolution and metadata for supported Minecraft versions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from .exceptions import UnsupportedVersionError

_DATA_PKG = "leafish.data"
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
        return Path(str(resources.files(_DATA_PKG) / _VERSIONS_DIR))
    except (ModuleNotFoundError, FileNotFoundError, TypeError, ValueError):
        # Fallback for running from a source checkout.
        return Path(__file__).parent / "data" / "versions"


@lru_cache(maxsize=1)
def _cached_versions() -> tuple[str, ...]:
    root = _versions_root()
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            p.name
            for p in root.iterdir()
            if p.is_dir() and (p / "version.json").exists()
        )
    )


@lru_cache(maxsize=1)
def _protocol_to_version_map() -> dict[int, str]:
    mapping: dict[int, str] = {}
    for v in _cached_versions():
        proto = int(load_version_json(v, "version")["version"])
        mapping.setdefault(proto, v)
    return mapping


def list_versions() -> list[str]:
    """Return the Minecraft version strings for which data is vendored."""
    return list(_cached_versions())


def load_version_json(version: str, name: str) -> Any:
    """Load ``<name>.json`` for a vendored Minecraft *version*."""
    if (
        not version
        or not name
        or "/" in version
        or "\\" in version
        or ".." in version
        or "/" in name
        or "\\" in name
        or ".." in name
    ):
        raise UnsupportedVersionError(
            f"Invalid version or data name: {version!r}/{name!r}"
        )
    root = _versions_root().resolve()
    path = (root / version / f"{name}.json").resolve()
    if not path.is_relative_to(root):
        raise UnsupportedVersionError(
            f"Path escapes vendored data directory: {version!r}/{name!r}"
        )
    if not path.exists():
        raise UnsupportedVersionError(
            f"Minecraft {version} has no vendored '{name}' data"
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_version(requested: str) -> str:
    """Resolve ``requested`` (``"latest"`` or a version string) to a vendored version."""
    versions = _cached_versions()
    if requested != "latest":
        if requested not in versions:
            raise UnsupportedVersionError(
                f"Minecraft {requested} is not supported. "
                f"Available: {', '.join(versions) or '(none)'}"
            )
        return requested
    if not versions:
        raise UnsupportedVersionError("No Minecraft version data is vendored")
    # "latest" = highest protocol version (string sort is wrong for e.g.
    # "1.9" vs "1.10" and for the year-based "26.x" line).
    proto_map = _protocol_to_version_map()
    return proto_map[max(proto_map)]


def version_for_protocol(protocol_version: int) -> str | None:
    """Return the vendored version matching *protocol_version*, if any."""
    return _protocol_to_version_map().get(protocol_version)


def get_version_info(version: str) -> VersionInfo:
    """Return protocol metadata for a vendored *version*."""
    resolved = resolve_version(version)
    vjson = load_version_json(resolved, "version")
    return VersionInfo(
        minecraft_version=resolved,
        protocol_version=int(vjson["version"]),
        data_dir=_versions_root() / resolved,
    )
