"""World model: chunks, blocks, dimensions, time and weather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..data.registry import GameData, get_gamedata
from ..utils.geometry import raycast_voxels
from ..utils.vectors import BlockPos, Vec3
from .block import Block

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.world")


class Chunk:
    """A 16x16 column of chunk sections."""

    __slots__ = ("block_entities", "heightmaps", "sections", "x", "z")

    def __init__(self, x: int, z: int) -> None:
        self.x = x
        self.z = z
        self.sections: dict[int, ChunkSection] = {}
        self.block_entities: list[dict] = []
        self.heightmaps: dict[str, Any] = {}


class ChunkSection:
    """One 16x16x16 section of blocks (palette + packed indices)."""

    __slots__ = ("block_states", "data", "non_air_count", "palette", "y")

    def __init__(self, y: int) -> None:
        self.y = y
        self.block_states: list[int] = []
        self.palette: list[int] = []
        self.data: list[int] = []
        self.non_air_count = 0


class World:
    """The bot's view of the Minecraft world."""

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

    # -- chunks -----------------------------------------------------------------

    def chunk_at(self, cx: int, cz: int) -> Chunk | None:
        return self.chunks.get((cx, cz))

    def load_chunk(self, cx: int, cz: int) -> Chunk:
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            chunk = Chunk(cx, cz)
            self.chunks[(cx, cz)] = chunk
        return chunk

    def unload_chunk(self, cx: int, cz: int) -> None:
        self.chunks.pop((cx, cz), None)

    # -- blocks -------------------------------------------------------------------

    def block_at(self, pos: BlockPos | Vec3 | tuple) -> Block | None:
        """Return the Block at *pos*, or ``None`` if the chunk isn't loaded."""
        if isinstance(pos, Vec3):
            bp = pos.floor()
        elif isinstance(pos, tuple):
            bp = BlockPos(*pos)
        else:
            bp = pos
        chunk = self.chunk_at(bp.x >> 4, bp.z >> 4)
        if chunk is None:
            return None
        section_y = bp.y >> 4
        section = chunk.sections.get(section_y)
        if section is None or not section.block_states:
            return self._block_for_state(0, bp)
        lx = bp.x & 15
        ly = bp.y & 15
        lz = bp.z & 15
        idx = (ly << 8) | (lz << 4) | lx
        if idx >= len(section.block_states):
            return self._block_for_state(0, bp)
        state_id = section.block_states[idx]
        return self._block_for_state(state_id, bp)

    def _block_for_state(self, state_id: int, pos: BlockPos) -> Block | None:
        resolved = self.gamedata.block_state(state_id)
        if resolved is None:
            return None
        block_data, state_data = resolved
        return Block(
            state_id=state_id,
            block_id=block_data.get("id", state_id),
            name=block_data.get("name", "air"),
            position=pos,
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

    def set_block_state(self, pos: BlockPos | Vec3, state_id: int) -> None:
        """Update the local block state at *pos* (from block_update packets)."""
        bp = pos.floor() if isinstance(pos, Vec3) else pos
        chunk = self.chunk_at(bp.x >> 4, bp.z >> 4)
        if chunk is None:
            return
        section_y = bp.y >> 4
        section = chunk.sections.get(section_y)
        if section is None:
            return
        lx, ly, lz = bp.x & 15, bp.y & 15, bp.z & 15
        idx = (ly << 8) | (lz << 4) | lx
        if idx < len(section.block_states):
            section.block_states[idx] = state_id

    def find_blocks(
        self,
        names: str | list[str],
        *,
        max_distance: int = 32,
        count: int = 1,
    ) -> list[BlockPos]:
        """Find block positions matching *names* near the bot."""
        if isinstance(names, str):
            names = [names]
        wanted = {self.gamedata.block_state_id(n) for n in names}
        wanted.discard(None)
        origin = self.bot.entity.position.floor() if self.bot.entity else BlockPos(0, 0, 0)
        found: list[BlockPos] = []
        for (cx, cz), chunk in self.chunks.items():
            for section in chunk.sections.values():
                if not section.block_states:
                    continue
                for idx, sid in enumerate(section.block_states):
                    if sid not in wanted:
                        continue
                    ly = idx >> 8
                    rem = idx & 0xFF
                    lz = rem >> 4
                    lx = rem & 0xF
                    pos = BlockPos(
                        (cx << 4) + lx,
                        (section.y << 4) + ly,
                        (cz << 4) + lz,
                    )
                    if pos.distance_squared_to(origin) > max_distance ** 2:
                        continue
                    found.append(pos)
                    if len(found) >= count * 4:
                        return found[:count] if count else found
        return found[:count] if count else found

    def find_block(self, names: str | list[str], **kwargs) -> Block | None:
        positions = self.find_blocks(names, count=1, **kwargs)
        if not positions:
            return None
        return self.block_at(positions[0])

    def can_dig_block(self, block: Block | None) -> bool:
        """Whether the bot could dig *block* (basic checks; tool logic later)."""
        if block is None:
            return False
        return (block.diggable and block.hardness > 0) or block.hardness == 0

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
