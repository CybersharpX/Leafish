"""Fetch minecraft-data JSON files for Leafish versions.

Downloads the data files listed in minecraft-data's ``dataPaths.json`` for the
requested Minecraft versions and stores them under
``src/leafish/data/versions/<version>/``. No Node.js is required — the files
are plain JSON served from the minecraft-data GitHub repository.

Usage:
    python tools/fetch_mcdata.py 1.21.11
    python tools/fetch_mcdata.py --all-stable
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO = "https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master"
DATA_PATHS_URL = f"{REPO}/data/dataPaths.json"

#: Data files Leafish needs, mapped to the dataPaths key.
NEEDED = [
    "protocol",
    "proto",
    "blocks",
    "items",
    "entities",
    "recipes",
    "biomes",
    "windows",
    "version",
    "blockCollisionShapes",
    "effects",
    "enchantments",
    "foods",
    "materials",
    "particles",
    "attributes",
    "loginPacket",
    "sounds",
    "tints",
    "mapIcons",
    "blockLoot",
    "entityLoot",
    "commands",
    "language",
]

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_DIR = ROOT / "src" / "leafish" / "data" / "versions"


def fetch_json(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "leafish-fetch"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def load_data_paths() -> dict:
    return json.loads(fetch_json(DATA_PATHS_URL))


def fetch_version(version: str, paths: dict, dry_run: bool = False) -> list[str]:
    pc = paths.get("pc", {})
    if version not in pc:
        raise SystemExit(f"Unknown Minecraft version in dataPaths: {version}")
    mapping = pc[version]
    out_dir = VERSIONS_DIR / version
    fetched: list[str] = []
    for key in NEEDED:
        rel = mapping.get(key)
        if not rel:
            continue
        # rel looks like "pc/1.21.11" — files are <rel>/<key>.json
        url = f"{REPO}/data/{rel}/{key}.json"
        target = out_dir / f"{key}.json"
        if dry_run:
            print(f"  would fetch {url} -> {target}")
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = fetch_json(url)
        except Exception as exc:
            print(f"  ! failed {key}: {exc}", file=sys.stderr)
            continue
        target.write_bytes(data)
        fetched.append(key)
        print(f"  {key}: {len(data) / 1024:.0f} KiB")
    return fetched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("versions", nargs="*", help="Minecraft versions to fetch")
    parser.add_argument("--all-stable", action="store_true",
                        help="Fetch every 1.x version directory (slow)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = load_data_paths()
    versions = args.versions
    if args.all_stable:
        versions = sorted(
            k for k in paths["pc"]
            if k.startswith("1.") and "-" not in k and "w" not in k.lower()
        )
    if not versions:
        parser.error("specify at least one version or --all-stable")

    for version in versions:
        print(f"Fetching minecraft-data for {version}...")
        fetched = fetch_version(version, paths, dry_run=args.dry_run)
        print(f"  -> {len(fetched)} files")


if __name__ == "__main__":
    main()
