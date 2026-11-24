"""World model: chunks, blocks, dimensions, time and weather."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from ..data.registry import GameData, get_gamedata
from ..utils.geometry import raycast_voxels
from ..utils.vectors import BlockPos, Vec3
from .block import Block
from .chunk_codec import (
    BIOME_SECTION_VOLUME,
    BLOCK_SECTION_VOLUME,
    ChunkSectionData,
    PalettedContainer,
)

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.world")


class ChunkSection:
    """One 16x16x16 section of blocks (paletted container storage)."""

    __slots__ = ("biomes", "blocks", "fluid_count", "non_air_count", "states", "y")

    def __init__(
        self,
        y: int,
        blocks: PalettedContainer | None = None,
        biomes: PalettedContainer | None = None,
        non_air_count: int = 0,
        fluid_count: int = 0,
    ) -> None:
        self.y = y
        # ``states`` is a lazily materialized list used after local edits;
        # while ``None`` the packed ``blocks`` container is authoritative.
        self.states: list[int] | None = None
        self.blocks = blocks
        self.biomes = biomes
        self.non_air_count = non_air_count
        self.fluid_count = fluid_count

    @classmethod
    def from_data(cls, data: ChunkSectionData) -> ChunkSection:
        section = cls(
            data.y,
            blocks=data.block_states if not isinstance(data.block_states, list) else None,
            biomes=data.biomes,
            non_air_count=data.non_air_count,
            fluid_count=data.fluid_count,
        )
        if isinstance(data.block_states, list):
            # Legacy (1.8) sections arrive as a plain list of state ids.
            section.states = data.block_states
        return section

    # -- block states ---------------------------------------------------------

    def get_state(self, index: int) -> int:
        """Global block-state id at section-local *index* (0..4095)."""
        if self.states is not None:
            return self.states[index]
        if self.blocks is None:
            return 0
        return self.blocks.get(index)

    def iter_states(self):
        if self.states is not None:
            return iter(self.states)
        if self.blocks is None:
            return iter([0] * BLOCK_SECTION_VOLUME)
        return self.blocks.values()

    def set_state(self, index: int, state_id: int) -> None:
        if self.states is None:
            # Materialize once so subsequent edits stay cheap.
            self.states = (
                self.blocks.to_list() if self.blocks is not None else [0] * BLOCK_SECTION_VOLUME
            )
        self.states[index] = state_id

    # -- biomes -----------------------------------------------------------------

    def biome_at(self, index: int) -> int:
        """Biome registry id at biome-cell *index* (0..63)."""
        if self.biomes is None:
            return 0
        return self.biomes.get(index)


class Chunk:
    """A 16x16 column of chunk sections."""

    __slots__ = ("block_entities", "heightmaps", "light", "sections", "x", "z")

    def __init__(self, x: int, z: int) -> None:
        self.x = x
        self.z = z
        self.sections: dict[int, ChunkSection] = {}
        self.block_entities: list[dict] = []
        self.heightmaps: dict[str, Any] = {}
        #: ``section_y -> (sky_light_bytes|None, block_light_bytes|None)``.
        #: Each entry is a 2048-byte nibble array (4096 light values).
        self.light: dict[int, tuple[bytes | None, bytes | None]] = {}


class World:
    """The bot's view of the Minecraft world."""

    # Maximum number of distinct block state prototypes to cache.  Vanilla
    # 1.21 has ≈26 000 block states; a cap of 8 192 covers the most common
    # ones and keeps memory bounded.
    _BLOCK_CACHE_SIZE = 8192

    def __init__(self, bot: LeafishBot, version: str) -> None:
        self.bot = bot
        self.gamedata: GameData = get_gamedata(version)
        self.chunks: dict[tuple[int, int], Chunk] = {}
        self.dimension: str | None = None
        self.time: int = 0
        self.time_of_day: int = 0
        self.weather: dict[str, Any] = {}
        self.min_y: int = -64
        self.height: int = 384
        # Registry data captured during the configuration state.
        self.dimension_types: dict[str, dict[str, Any]] = {}
        self.dimensions: dict[str, dict[str, Any]] = {}
        self.biome_count: int = 0
        self.spawn_point: BlockPos | None = None
        """World spawn position (from ``spawn_position``/respawn data)."""

        # Block prototype cache: maps state_id → Block built without a
        # position.  ``block_at`` stamps in the actual position before
        # returning, avoiding repeated registry lookups for common states.
        self._block_proto_cache: dict[int, Block] = {}
        self._cache_lock = threading.RLock()

    # -- dimensions ---------------------------------------------------------------

    @property
    def min_section_y(self) -> int:
        return self.min_y >> 4

    @property
    def section_count(self) -> int:
        return self.height >> 4

    def set_dimension_bounds(self, min_y: int, height: int) -> None:
        """Update vertical bounds (from the dimension_type registry)."""
        if min_y != self.min_y or height != self.height:
            self.min_y, self.height = min_y, height
            # Bounds changed: previously decoded sections may be misaligned.
            self.chunks.clear()

    def apply_dimension(self, name: str | None, dimension_id: int | None = None) -> None:
        """Select the active dimension's vertical bounds from registries."""
        dim_type_key: str | None = None
        entry = self.dimensions.get(name) if name else None
        if entry is not None:
            dim_type_key = entry.get("type")
        if dim_type_key is None and dimension_id is not None:
            # Fallback: dimension varint indexes the registry entry order.
            keys = list(self.dimensions)
            if 0 <= dimension_id < len(keys):
                dim_type_key = self.dimensions[keys[dimension_id]].get("type")
        if dim_type_key is None and name in self.dimension_types:
            dim_type_key = name
        if dim_type_key is None:
            # Vanilla overworld defaults.
            self.set_dimension_bounds(-64, 384)
            return
        info = self.dimension_types.get(dim_type_key)
        if info is None:
            self.set_dimension_bounds(-64, 384)
            return
        min_y = int(info.get("min_y", -64))
        height = int(info.get("height", 384))
        self.set_dimension_bounds(min_y, height)
        self.dimension = name

    # -- chunks -----------------------------------------------------------------

    def chunk_at(self, cx: int, cz: int) -> Chunk | None:
        return self.chunks.get((cx, cz))

    def load_chunk(self, cx: int, cz: int) -> Chunk:
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            chunk = Chunk(cx, cz)
            self.chunks[(cx, cz)] = chunk
        return chunk

    def load_chunk_data(
        self,
        cx: int,
        cz: int,
        sections: list[ChunkSectionData],
        *,
        heightmaps: dict[str, Any] | None = None,
        block_entities: list[dict] | None = None,
    ) -> Chunk:
        """Store a fully decoded chunk column."""
        chunk = self.load_chunk(cx, cz)
        chunk.sections = {
            s.y: ChunkSection.from_data(s) for s in sections
        }
        if heightmaps is not None:
            chunk.heightmaps = heightmaps
        if block_entities is not None:
            chunk.block_entities = block_entities
        return chunk

    def unload_chunk(self, cx: int, cz: int) -> None:
        self.chunks.pop((cx, cz), None)

    # -- lighting ---------------------------------------------------------------

    @staticmethod
    def _mask_sections(
        mask: list[int], empty_mask: list[int], arrays: list[Any],
        min_section_y: int,
    ) -> dict[int, bytes]:
        """Map light-update bitmask bits to per-section nibble arrays.

        Bit ``i`` of the mask covers section ``min_section_y - 1 + i``
        (the masks span ``section_count + 2`` bits). Bits set in
        ``empty_mask`` have all-zero data and consume no array entry.
        """
        result: dict[int, bytes] = {}
        # Combine i64 words into one big int (masks arrive as lists).
        value = 0
        for i, word in enumerate(mask):
            value |= (int(word) & 0xFFFFFFFFFFFFFFFF) << (64 * i)
        empty = 0
        for i, word in enumerate(empty_mask):
            empty |= (int(word) & 0xFFFFFFFFFFFFFFFF) << (64 * i)
        idx = 0
        for bit in range(len(mask) * 64):
            if (value >> bit) & 1:
                section_y = min_section_y - 1 + bit
                if (empty >> bit) & 1:
                    result[section_y] = b""
                elif idx < len(arrays):
                    result[section_y] = bytes(arrays[idx])
                    idx += 1
        return result

    def apply_light_update(self, cx: int, cz: int, params: dict[str, Any]) -> None:
        """Store light data from an ``update_light`` packet."""
        chunk = self.chunk_at(int(cx), int(cz))
        if chunk is None:
            chunk = self.load_chunk(int(cx), int(cz))
        min_sy = self.min_section_y
        sky = self._mask_sections(
            params.get("skyLightMask") or [],
            params.get("emptySkyLightMask") or [],
            params.get("skyLight") or [],
            min_sy,
        )
        block = self._mask_sections(
            params.get("blockLightMask") or [],
            params.get("emptyBlockLightMask") or [],
            params.get("blockLight") or [],
            min_sy,
        )
        section_ys = set(sky) | set(block)
        for sy in section_ys:
            sky_data = sky.get(sy)
            block_data = block.get(sy)
            chunk.light[sy] = (
                None if sky_data is None else sky_data,
                None if block_data is None else block_data,
            )

    @staticmethod
    def _nibble(data: bytes, index: int) -> int:
        """Read nibble *index* (0..4095) from a 2048-byte packed array."""
        if index >> 1 >= len(data):
            return 0
        byte = data[index >> 1]
        return (byte >> ((index & 1) * 4)) & 0xF

    def light_at(self, pos: BlockPos | Vec3 | tuple) -> tuple[int | None, int | None]:
        """Return ``(sky_light, block_light)`` at *pos*.

        ``None`` means no light data was received for that section.
        """
        bp = self._to_block_pos(pos)
        chunk = self.chunk_at(bp.x >> 4, bp.z >> 4)
        if chunk is None:
            return None, None
        entry = chunk.light.get(bp.y >> 4)
        if entry is None:
            return None, None
        idx = ((bp.y & 15) << 8) | ((bp.z & 15) << 4) | (bp.x & 15)
        sky, block = entry
        return (
            self._nibble(sky, idx) if sky else (0 if sky == b"" else None),
            self._nibble(block, idx) if block else (0 if block == b"" else None),
        )

    # -- blocks -------------------------------------------------------------------

    def block_at(self, pos: BlockPos | Vec3 | tuple) -> Block | None:
        """Return the Block at *pos*, or ``None`` if the chunk isn't loaded."""
        bp = self._to_block_pos(pos)
        chunk = self.chunk_at(bp.x >> 4, bp.z >> 4)
        if chunk is None:
            return None
        section_y = bp.y >> 4
        section = chunk.sections.get(section_y)
        if section is None:
            return self._block_for_state(0, bp)
        lx = bp.x & 15
        ly = bp.y & 15
        lz = bp.z & 15
        idx = (ly << 8) | (lz << 4) | lx
        state_id = section.get_state(idx)
        return self._block_for_state(state_id, bp)

    @staticmethod
    def _to_block_pos(pos: BlockPos | Vec3 | tuple) -> BlockPos:
        if isinstance(pos, Vec3):
            return pos.floor()
        if isinstance(pos, tuple):
            return BlockPos(*pos)
        return pos

    # Sentinel used as the position stored in every cached prototype.
    # The correct position is always stamped in before the caller sees it.
    _PROTO_POS = BlockPos(0, 0, 0)

    def _block_for_state(self, state_id: int, pos: BlockPos) -> Block | None:
        # Fast path: thread-safe prototype cache lookup.
        with self._cache_lock:
            proto = self._block_proto_cache.get(state_id)
        if proto is not None:
            b = Block.__new__(Block)
            b.__dict__ = proto.__dict__.copy()
            b.position = pos
            return b

        resolved = self.gamedata.block_state(state_id)
        if resolved is None:
            return None
        block_data, state_data = resolved
        proto = Block(
            state_id=state_id,
            block_id=block_data.get("id", state_id),
            name=block_data.get("name", "air"),
            position=self._PROTO_POS,
            hardness=block_data.get("hardness", 0.0),
            diggable=block_data.get("diggable", False),
            material=block_data.get("material"),
            transparent=block_data.get("transparent", False),
            emit_light=block_data.get("emitLight", 0),
            filter_light=block_data.get("filterLight", 0),
            states=block_data.get("states", []),
            bounding_box=block_data.get("boundingBox", "block"),
            state_properties=state_data.get("properties", {}),
        )
        with self._cache_lock:
            if len(self._block_proto_cache) >= self._BLOCK_CACHE_SIZE:
                oldest = next(iter(self._block_proto_cache))
                del self._block_proto_cache[oldest]
            self._block_proto_cache[state_id] = proto

        result = Block.__new__(Block)
        result.__dict__ = proto.__dict__.copy()
        result.position = pos
        return result

    def set_block_state(self, pos: BlockPos | Vec3, state_id: int) -> None:
        """Update the local block state at *pos* (from block_update packets)."""
        bp = self._to_block_pos(pos)
        chunk = self.chunk_at(bp.x >> 4, bp.z >> 4)
        if chunk is None:
            return
        section_y = bp.y >> 4
        section = chunk.sections.get(section_y)
        if section is None:
            return
        lx, ly, lz = bp.x & 15, bp.y & 15, bp.z & 15
        idx = (ly << 8) | (lz << 4) | lx
        section.set_state(idx, state_id)

    def find_blocks(
        self,
        names: str | list[str],
        *,
        max_distance: int = 32,
        count: int = 1,
    ) -> list[BlockPos]:
        """Find block positions matching *names* near the bot, sorted by distance."""
        if isinstance(names, str):
            names = [names]
        wanted: set[int] = set()
        for n in names:
            wanted.update(self.gamedata.block_state_ids(n))
        if not wanted:
            return []
        origin = self.bot.entity.position.floor() if self.bot.entity else BlockPos(0, 0, 0)
        ox, oy, oz = origin.x, origin.y, origin.z
        max_dist_sq = max_distance * max_distance
        found: list[BlockPos] = []
        # Sort chunks by minimum possible horizontal distance to origin.
        def _chunk_dist_sq(item: tuple[tuple[int, int], Chunk]) -> int:
            cx, cz = item[0]
            dx = max((cx << 4) - ox, 0, ox - ((cx << 4) + 15))
            dz = max((cz << 4) - oz, 0, oz - ((cz << 4) + 15))
            return dx * dx + dz * dz

        for (cx, cz), chunk in sorted(self.chunks.items(), key=_chunk_dist_sq):
            base_x = cx << 4
            base_z = cz << 4
            dx = max(base_x - ox, 0, ox - (base_x + 15))
            dz = max(base_z - oz, 0, oz - (base_z + 15))
            horiz_sq = dx * dx + dz * dz
            if horiz_sq > max_dist_sq:
                break  # all remaining chunks are even farther
            for section in chunk.sections.values():
                base_y = section.y << 4
                dy = max(base_y - oy, 0, oy - (base_y + 15))
                if horiz_sq + dy * dy > max_dist_sq:
                    continue
                # Fast-path skip for paletted sections that cannot match.
                if section.states is None and section.blocks is not None:
                    pal = section.blocks.palette
                    if pal is not None and not wanted.intersection(pal):
                        continue
                for idx, sid in enumerate(section.iter_states()):
                    if sid not in wanted:
                        continue
                    ly = idx >> 8
                    rem = idx & 0xFF
                    lz = rem >> 4
                    lx = rem & 0xF
                    bx = base_x + lx
                    by = base_y + ly
                    bz = base_z + lz
                    if (bx - ox) ** 2 + (by - oy) ** 2 + (bz - oz) ** 2 > max_dist_sq:
                        continue
                    found.append(BlockPos(bx, by, bz))
        found.sort(key=lambda p: p.distance_squared_to(origin))
        return found[:count] if count else found

    def find_block(self, names: str | list[str], **kwargs) -> Block | None:
        positions = self.find_blocks(names, count=1, **kwargs)
        if not positions:
            return None
        return self.block_at(positions[0])

    def biome_at(self, pos: BlockPos | Vec3 | tuple) -> dict[str, Any] | None:
        """Return the biome metadata dictionary for *pos*."""
        bp = self._to_block_pos(pos)
        chunk = self.chunk_at(bp.x >> 4, bp.z >> 4)
        if chunk is None:
            return None
        section_y = bp.y >> 4
        section = chunk.sections.get(section_y)
        if section is None:
            return None
        # 4x4x4 biome grid within the 16x16x16 section
        lx = (bp.x & 15) >> 2
        ly = (bp.y & 15) >> 2
        lz = (bp.z & 15) >> 2
        idx = (ly << 4) | (lz << 2) | lx
        biome_id = section.biome_at(idx)
        return self.gamedata.biome_by_id(biome_id)

    def can_dig_block(self, block: Block | None) -> bool:
        """Whether the bot could dig *block*."""
        if block is None or block.is_air:
            return False
        return bool(block.diggable) and block.hardness >= 0

    def raycast(
        self,
        origin: Vec3,
        direction: Vec3,
        max_distance: float,
        *,
        predicate=None,
    ):
        """Raycast against loaded blocks; returns first matching Block."""
        def is_solid(pos: BlockPos) -> bool:
            block = self.block_at(pos)
            if block is None:
                return False
            solid = not block.transparent
            if predicate is not None:
                return predicate(block)
            return solid

        hit = raycast_voxels(origin, direction, max_distance, is_solid)
        if hit is None:
            return None
        return self.block_at(hit.position), hit

    # -- state ---------------------------------------------------------------------

    def set_time(self, age: int, time: int, tick_day_time: bool) -> None:
        self.time = age
        self.time_of_day = time

    def set_weather(self, params: dict[str, Any]) -> None:
        self.weather.update(params)


__all__ = [
    "BIOME_SECTION_VOLUME",
    "BLOCK_SECTION_VOLUME",
    "Chunk",
    "ChunkSection",
    "ChunkSectionData",
    "PalettedContainer",
    "World",
]
