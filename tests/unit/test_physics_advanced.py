"""Additional physics tests: conditional position send, block-cache."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from leafish.modules.physics import PhysicsEngine
from leafish.utils.vectors import BlockPos, Vec3
from leafish.world.block import Block

# ---------------------------------------------------------------------------
# Shared stubs (duplicated from test_physics.py for isolation)
# ---------------------------------------------------------------------------


def _solid_block(x: int, y: int, z: int) -> Block:
    return Block(
        state_id=1, block_id=1, name="stone",
        position=BlockPos(x, y, z), bounding_box="block",
    )


class _World:
    def __init__(self, blocks: dict) -> None:
        self._blocks = blocks

    def block_at(self, pos) -> Block | None:
        bp = pos.floor() if isinstance(pos, Vec3) else pos
        return self._blocks.get((bp.x, bp.y, bp.z))


class _Entity:
    def __init__(self, pos: Vec3) -> None:
        self.position = pos
        self.velocity = Vec3(0, 0, 0)
        self.yaw = 0.0
        self.pitch = 0.0
        self.on_ground = False
        self.eye_height = 1.62

    def set_position(self, x, y, z, *, absolute=True):
        self.position = Vec3(x, y, z)

    def floor(self):
        return self.position.floor()


class _Bot:
    def __init__(self, world: _World, pos: Vec3) -> None:
        self.world = world
        self.entity = _Entity(pos)
        self.control_states = {c: False for c in
                               ("forward", "backward", "left", "right",
                                "jump", "sneak", "sprint")}
        self.game_mode = "survival"
        self.sent: list[tuple[str, dict]] = []

    async def _send_play(self, name, params=None):
        self.sent.append((name, params or {}))

    def emit(self, *a, **k):
        pass


def _floor_world() -> _World:
    blocks = {}
    for x in range(-2, 4):
        for z in range(-2, 4):
            blocks[(x, 63, z)] = _solid_block(x, 63, z)
    return _World(blocks)


# ---------------------------------------------------------------------------
# Conditional position send
# ---------------------------------------------------------------------------


def test_first_tick_always_sends():
    """The very first tick always sends a position packet (no prior state)."""
    bot = _Bot(_floor_world(), Vec3(0.5, 64.0, 0.5))
    engine = PhysicsEngine(cast(Any, bot))

    asyncio.run(engine.tick())
    sent_names = [name for name, _ in bot.sent]
    assert "position_look" in sent_names


def test_stationary_bot_sends_every_20_ticks():
    """A bot standing still sends a heartbeat every 20 ticks after the first packet."""
    bot = _Bot(_floor_world(), Vec3(0.5, 64.0, 0.5))
    engine = PhysicsEngine(cast(Any, bot))

    # Tick 1: first packet (initialises state, _ticks_since_send resets to 0).
    asyncio.run(engine.tick())
    assert len(bot.sent) == 1

    # Ticks 2-20: stationary, no changes → 19 more ticks, counter goes 1→19.
    for _ in range(19):
        asyncio.run(engine.tick())
    assert len(bot.sent) == 1  # still just the first packet

    # Tick 21: _ticks_since_send reaches 20 → heartbeat fires.
    asyncio.run(engine.tick())
    assert len(bot.sent) == 2


def test_moving_bot_sends_every_tick():
    """When the bot's position changes each tick, a packet is sent each tick."""
    bot = _Bot(_floor_world(), Vec3(0.5, 64.0, 0.5))
    engine = PhysicsEngine(cast(Any, bot))

    # Drive the bot forward for 5 ticks.
    bot.control_states["forward"] = True
    for _ in range(5):
        asyncio.run(engine.tick())

    # Should have sent at least 5 position packets (one per changed tick).
    pos_packets = sum(1 for name, _ in bot.sent if name == "position_look")
    assert pos_packets >= 5


# ---------------------------------------------------------------------------
# Block prototype cache (World._block_proto_cache)
# ---------------------------------------------------------------------------


def test_block_cache_returns_same_type_different_positions():
    """block_at() for the same state_id at different positions should return
    Block objects with equal type info but correct individual positions."""
    from unittest.mock import MagicMock, patch

    from leafish.utils.vectors import BlockPos
    from leafish.world.world import World

    # Build a minimal mock bot + world.
    mock_bot = MagicMock()
    world = World(mock_bot, "1.21.11")

    # Inject a fake block state entry into the gamedata resolver.
    fake_block_data = {
        "id": 42, "name": "stone", "hardness": 1.5,
        "diggable": True, "material": "rock",
        "transparent": False, "emitLight": 0, "filterLight": 15,
        "states": [], "boundingBox": "block",
    }
    fake_state_data = {"properties": {}}

    with patch.object(world.gamedata, "block_state",
                      return_value=(fake_block_data, fake_state_data)):
        pos1 = BlockPos(10, 64, 10)
        pos2 = BlockPos(20, 64, 20)

        b1 = world._block_for_state(1, pos1)
        b2 = world._block_for_state(1, pos2)

        # Same type info.
        assert b1 is not None and b2 is not None
        assert b1.name == b2.name == "stone"
        assert b1.state_id == b2.state_id == 1

        # But different positions.
        assert b1.position == pos1
        assert b2.position == pos2

        # Cache should now have the prototype.
        assert 1 in world._block_proto_cache
        # Prototype's position is the sentinel (0, 0, 0).
        proto = world._block_proto_cache[1]
        assert proto.position == BlockPos(0, 0, 0)


def test_block_cache_hit_avoids_gamedata_call():
    """Second lookup for the same state_id uses the cache (no second registry call)."""
    from unittest.mock import MagicMock, patch

    from leafish.utils.vectors import BlockPos
    from leafish.world.world import World

    mock_bot = MagicMock()
    world = World(mock_bot, "1.21.11")

    fake_block_data = {
        "id": 1, "name": "stone", "hardness": 1.5, "diggable": True,
        "material": "rock", "transparent": False, "emitLight": 0,
        "filterLight": 15, "states": [], "boundingBox": "block",
    }

    with patch.object(world.gamedata, "block_state",
                      return_value=(fake_block_data, {"properties": {}})) as mock_gs:
        world._block_for_state(1, BlockPos(0, 64, 0))
        world._block_for_state(1, BlockPos(1, 64, 0))
        world._block_for_state(1, BlockPos(2, 64, 0))

        # block_state() should only have been called once — subsequent hits
        # come from the prototype cache.
        assert mock_gs.call_count == 1
