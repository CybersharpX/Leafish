"""Game-data registry: resolves names/ids for blocks, items, entities, etc."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ..version import load_version_json, resolve_version


class GameData:
    """Loaded minecraft-data registries for one Minecraft version."""

    def __init__(self, version: str) -> None:
        self.version = resolve_version(version)
        self._raw: dict[str, Any] = {}
        self._blocks_by_name: dict[str, dict] = {}
        self._blocks_by_id: dict[int, dict] = {}
        self._block_states: dict[int, tuple[dict, dict]] = {}
        self._items_by_name: dict[str, dict] = {}
        self._items_by_id: dict[int, dict] = {}
        self._entities_by_name: dict[str, dict] = {}
        self._entity_type_ids: dict[int, str] = {}
        self._biomes_by_id: dict[int, dict] = {}
        self._biomes_by_name: dict[str, dict] = {}
        self._state_ranges: list[tuple[int, int, dict]] = []
        self._state_range_starts: list[int] = []
        self._loaded = False

    # -- lazy loading -----------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._load("blocks")
        self._load("items")
        self._load("entities")
        self._load("recipes")
        self._load("biomes")
        self._index_blocks()
        self._index_items()
        self._index_entities()
        self._index_biomes()

    def _load(self, name: str) -> None:
        try:
            self._raw[name] = load_version_json(self.version, name)
        except Exception:
            self._raw[name] = []

    def _index_blocks(self) -> None:
        for block in self._raw.get("blocks", []):
            self._blocks_by_name[block["name"]] = block
            self._blocks_by_id[block["id"]] = block
            states = block.get("states") or []
            if states and "id" in states[0]:
                # Legacy format: explicit per-state ids.
                for state in states:
                    self._block_states[state["id"]] = (block, state)
            elif block.get("minStateId") is not None:
                # Modern format: states are property descriptors; state ids are
                # computed by cartesian product (first property most significant).
                self._block_states[block.get("defaultState", block["id"])] = (block, {})
                lo, hi = block.get("minStateId"), block.get("maxStateId")
                if lo is not None and hi is not None:
                    self._state_ranges.append((lo, hi, block))
            else:
                # Pre-1.13 format: no state table; wire state ids are
                # ``(block_id << 4) | metadata``.
                self._index_legacy_block(block)
        self._state_ranges.sort()
        self._state_range_starts = [r[0] for r in self._state_ranges]

    def _index_legacy_block(self, block: dict) -> None:
        """Index a pre-1.13 block's ``(id << 4) | metadata`` state ids."""
        block_id = block.get("id")
        if block_id is None:
            return
        variations = block.get("variations") or []
        metas = {int(v.get("metadata", 0)) for v in variations if isinstance(v, dict)}
        if not metas:
            metas = {0}
        for meta in metas:
            state_id = (block_id << 4) | meta
            variation = next(
                (v for v in variations if int(v.get("metadata", 0)) == meta), None
            )
            props = {"metadata": meta}
            if variation is not None and variation.get("displayName"):
                props["variation"] = variation["displayName"]
            self._block_states[state_id] = (block, {"properties": props})

    def _index_items(self) -> None:
        for item in self._raw.get("items", []):
            self._items_by_name[item["name"]] = item
            self._items_by_id[item["id"]] = item

    def _index_entities(self) -> None:
        for ent in self._raw.get("entities", []):
            self._entities_by_name[ent["name"]] = ent
            # spawn_entity 'type' varint corresponds to the entity type
            # registry id; minecraft-data exposes it as 'id'.
            if "id" in ent:
                self._entity_type_ids[ent["id"]] = ent["name"]

    # -- blocks -----------------------------------------------------------------

    def block_by_name(self, name: str) -> dict | None:
        self._ensure_loaded()
        return self._blocks_by_name.get(name)

    def block_by_id(self, block_id: int) -> dict | None:
        self._ensure_loaded()
        return self._blocks_by_id.get(block_id)

    def block_state(self, state_id: int) -> tuple[dict, dict] | None:
        """Return ``(block, state-with-properties)`` for a global state id."""
        self._ensure_loaded()
        hit = self._block_states.get(state_id)
        if hit is not None:
            block, state = hit
            props = state.get("properties")
            if props is None and state_id != block.get("defaultState"):
                props = self._properties_for_state(block, state_id)
            return block, {"properties": props or {}}
        # State id may belong to a block with descriptor-style states.
        import bisect

        ranges = self._state_ranges
        # Binary search on range start.
        idx = bisect.bisect_right(self._state_range_starts, state_id) - 1
        if 0 <= idx < len(ranges):
            lo, hi, block = ranges[idx]
            if lo <= state_id <= hi:
                return block, {"properties": self._properties_for_state(block, state_id)}
        # Pre-1.13 fallback: ``state_id = (block_id << 4) | metadata``.
        legacy = self._blocks_by_id.get(state_id >> 4)
        if legacy is not None and legacy.get("minStateId") is None:
            meta = state_id & 0xF
            return legacy, {"properties": {"metadata": meta}}
        return None

    # -- state id math -----------------------------------------------------------

    @staticmethod
    def _prop_values(prop: dict) -> list:
        if prop.get("type") == "bool":
            return [False, True]
        return list(prop.get("values", []))

    def _properties_for_state(self, block: dict, state_id: int) -> dict[str, Any]:
        """Decompose *state_id* into property values for descriptor-style blocks."""
        states = block.get("states") or []
        if not states:
            return {}
        offset = state_id - block.get("minStateId", block.get("defaultState", 0))
        props: dict[str, Any] = {}
        # Last property varies fastest -> decompose from the end.
        for prop in reversed(states):
            values = self._prop_values(prop)
            n = len(values)
            if n == 0:
                continue
            idx = offset % n
            offset //= n
            props[prop["name"]] = values[idx] if idx < len(values) else values[0]
        return props

    def _state_offset(self, block: dict, properties: dict) -> int:
        """Compute the state-id offset for *properties* on descriptor blocks."""
        states = block.get("states") or []
        offset = 0
        stride = 1
        # Iterate reversed so the last property is the least significant digit.
        for prop in reversed(states):
            values = self._prop_values(prop)
            if not values:
                continue
            desired = properties.get(prop["name"], values[0])
            try:
                idx = values.index(desired)
            except ValueError:
                idx = 0
            offset += idx * stride
            stride *= len(values)
        return offset

    def block_state_id(self, name: str, properties: dict | None = None) -> int | None:
        """Find the state id for block *name* with matching properties."""
        self._ensure_loaded()
        block = self._blocks_by_name.get(name)
        if block is None:
            return None
        states = block.get("states") or []
        if not states:
            if block.get("minStateId") is None:
                # Pre-1.13: state id is ``(block_id << 4) | metadata``.
                meta = int((properties or {}).get("metadata", 0))
                return (block["id"] << 4) | meta
            return block.get("defaultState", block["id"])
        if states and "id" in states[0]:
            # Legacy format: match explicit per-state entries.
            if not properties:
                return block.get("defaultState")
            for state in states:
                props = state.get("properties", {})
                if all(props.get(k) == v for k, v in properties.items()):
                    return state["id"]
            return None
        if not properties:
            return block.get("defaultState")
        # Descriptor format: compute offset from minStateId.
        base = block.get("minStateId")
        if base is None:
            return block.get("defaultState")
        return base + self._state_offset(block, properties)

    def block_state_ids(self, name: str) -> set[int]:
        """Return all valid state IDs for block *name* across all its variations."""
        self._ensure_loaded()
        block = self._blocks_by_name.get(name)
        if block is None:
            return set()
        min_id = block.get("minStateId")
        max_id = block.get("maxStateId")
        if min_id is not None and max_id is not None:
            return set(range(min_id, max_id + 1))
        states = block.get("states")
        if states:
            ids = {s.get("id") for s in states if "id" in s}
            if ids:
                return ids
        if block.get("minStateId") is None and block.get("id") is not None:
            bid = block["id"]
            variations = block.get("variations") or []
            metas = {int(v.get("metadata", 0)) for v in variations if isinstance(v, dict)} or {0}
            return {(bid << 4) | m for m in metas}
        default = block.get("defaultState", block.get("id"))
        return {default} if default is not None else set()

    # -- items -------------------------------------------------------------------

    def item_by_name(self, name: str) -> dict | None:
        self._ensure_loaded()
        return self._items_by_name.get(name)

    def item_by_id(self, item_id: int) -> dict | None:
        self._ensure_loaded()
        return self._items_by_id.get(item_id)

    def item_name(self, item_id: int) -> str | None:
        item = self.item_by_id(item_id)
        return item["name"] if item else None

    # -- entities -----------------------------------------------------------------

    def entity_by_name(self, name: str) -> dict | None:
        self._ensure_loaded()
        return self._entities_by_name.get(name)

    def entity_type_name(self, type_id: int) -> str | None:
        self._ensure_loaded()
        return self._entity_type_ids.get(type_id)

    @property
    def entity_type_ids(self) -> dict[int, str]:
        self._ensure_loaded()
        return self._entity_type_ids

    # -- recipes ------------------------------------------------------------------

    def recipes(self) -> dict[str, Any]:
        """Raw ``recipes.json``: ``{recipe_id: [variant, ...]}``.

        Each variant has either ``inShape`` (grid of item ids / null) for
        shaped recipes or ``ingredients`` (list of item ids) for shapeless
        ones, plus ``result: {id, count}``.
        """
        self._ensure_loaded()
        return self._raw.get("recipes") or {}

    def item_id_by_name(self, name: str) -> int | None:
        item = self.item_by_name(name)
        return item["id"] if item else None

    # -- biomes -------------------------------------------------------------------

    def _index_biomes(self) -> None:
        for biome in self._raw.get("biomes", []):
            if isinstance(biome, dict):
                if "id" in biome:
                    self._biomes_by_id[biome["id"]] = biome
                if "name" in biome:
                    self._biomes_by_name[biome["name"]] = biome

    def biome_by_id(self, biome_id: int) -> dict | None:
        self._ensure_loaded()
        return self._biomes_by_id.get(biome_id)

    def biome_by_name(self, name: str) -> dict | None:
        self._ensure_loaded()
        return self._biomes_by_name.get(name)

    # -- misc ---------------------------------------------------------------------

    def raw(self, name: str) -> Any:
        self._ensure_loaded()
        return self._raw.get(name, [])


@lru_cache(maxsize=8)
def get_gamedata(version: str) -> GameData:
    """Cached GameData per Minecraft version."""
    return GameData(version)
