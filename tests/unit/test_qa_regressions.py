"""Regression tests for all defects identified and fixed during QA audit."""

from __future__ import annotations

import asyncio
import io
import os
import stat
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from leafish import Block, BlockPos, BotConfig, ConstructionPlan, FishingError, Vec3
from leafish.auth.microsoft import MicrosoftAuth
from leafish.auth.session import AuthSession
from leafish.bot import LeafishBot
from leafish.entities.entity import Player
from leafish.entities.manager import EntityManager
from leafish.events.emitter import EventEmitter
from leafish.exceptions import (
    PacketEncodeError,
    PluginError,
    ProtocolError,
    UnsupportedVersionError,
)
from leafish.modules.actions import ActionsModule
from leafish.modules.builder import BuilderModule
from leafish.pathfinder.goals import GoalNear, coerce_goal
from leafish.plugins import PluginManager, plugin
from leafish.protocol.compression import CompressionHandler
from leafish.protocol.connection import Connection
from leafish.protocol.encryption import AesCfb8Cipher
from leafish.protocol.framing import BufferWriter, encode_varint
from leafish.utils.nbt import (
    NBTLong,
    TAG_Compound,
    TAG_String,
    parse_snbt,
    read_compound,
    read_tag,
    write_compound,
)
from leafish.utils.text import component_to_text, strip_colors
from leafish.version import load_version_json
from leafish.world.chunk_codec import (
    ChunkDecodeError,
    PalettedContainer,
    _decode_container_v2,
    _Reader,
)
from leafish.world.world import World


def test_compression_decompression_bomb_rejected():
    handler = CompressionHandler(threshold=10, max_decompressed_size=1024)
    handler.enable(10)

    # 1. Declared length > max_decompressed_size
    bomb = zlib.compress(b"A" * 2048)
    with pytest.raises(ProtocolError, match="Invalid decompressed length"):
        handler.decompress_payload(encode_varint(2048) + bomb)

    # 2. Lying declared length (claims 10 bytes, actually decompresses to 2048 bytes)
    with pytest.raises(ProtocolError, match="exceeds declared length"):
        handler.decompress_payload(encode_varint(10) + bomb)

    # 3. Declared length larger than actual decompressed payload
    small = zlib.compress(b"hello world!" * 2)
    with pytest.raises(ProtocolError, match="mismatch"):
        handler.decompress_payload(encode_varint(500) + small)


def test_compression_negative_threshold_disables():
    handler = CompressionHandler()
    handler.enable(256)
    assert handler.enabled is True
    handler.enable(-1)
    assert handler.enabled is False
    assert handler.compress_payload(b"abc") == b"abc"


@pytest.mark.asyncio
async def test_connection_concurrent_encrypted_send_preserves_stream_order():
    secret = b"0123456789abcdef"
    written = bytearray()

    class _FakeWriter:
        def write(self, data: bytes) -> None:
            written.extend(data)

        async def drain(self) -> None:
            await asyncio.sleep(0)

    class _FakeCodec:
        def encode(self, state, direction, name, params):
            return name.encode("ascii")

    conn = Connection(_FakeCodec(), "localhost", 25565)  # type: ignore[arg-type]
    conn._writer = _FakeWriter()  # type: ignore[assignment]
    conn.enable_encryption(secret)

    await asyncio.gather(
        *(conn.send("play", "toServer", f"pkt{i}", {}) for i in range(20))
    )

    # Decrypting the single contiguous stream must recover all 20 valid frames.
    dec = AesCfb8Cipher(secret, secret)
    plain = dec.decrypt(bytes(written))
    assert len(plain) > 0
    for i in range(20):
        assert f"pkt{i}".encode("ascii") in plain


@pytest.mark.asyncio
async def test_microsoft_auth_xbl_identity_token_includes_uhs_and_redacts_repr(tmp_path: Path):
    posted: list[tuple[str, dict]] = []

    class _Resp:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code

        def json(self):
            return self._data

    class _FakeHttp:
        async def post(self, url, **kwargs):
            posted.append((url, kwargs.get("json") or kwargs.get("data") or {}))
            if "user.auth.xboxlive.com" in url:
                return _Resp({"Token": "xbl-tok", "DisplayClaims": {"xui": [{"uhs": "USERHASH123"}]}})
            if "xsts.auth.xboxlive.com" in url:
                return _Resp({"Token": "xsts-tok"})
            if "login_with_xbox" in url:
                return _Resp({"access_token": "mc-secret-token"})
            raise AssertionError(f"Unexpected POST {url}")

        async def get(self, url, **kwargs):
            return _Resp({"id": "0123456789abcdef0123456789abcdef", "name": "Alex"})

        async def aclose(self):
            pass

    cache = tmp_path / "tokens.json"
    auth = MicrosoftAuth(cache_path=cache, http_client=_FakeHttp())  # type: ignore[arg-type]
    auth._tokens["msa_access_token"] = "msa-tok"
    auth._tokens["msa_expires_at"] = 9999999999.0

    session = await auth.authenticate()
    assert session.username == "Alex"
    assert session.access_token == "mc-secret-token"
    assert "mc-secret-token" not in repr(session)

    mc_posts = [body for url, body in posted if "login_with_xbox" in url]
    assert mc_posts == [{"identityToken": "XBL3.0 x=USERHASH123;xsts-tok"}]

    # Cache file permissions must be owner-only (0600) on POSIX.
    if os.name == "posix":
        mode = stat.S_IMODE(cache.stat().st_mode)
        assert mode == 0o600


def test_bot_config_validation():
    with pytest.raises(ValueError, match="host"):
        BotConfig(host="")
    with pytest.raises(ValueError, match="port"):
        BotConfig(port=0)
    with pytest.raises(ValueError, match="port"):
        BotConfig(port=70000)
    with pytest.raises(ValueError, match="auth"):
        BotConfig(auth="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timeout"):
        BotConfig(timeout=0)
    with pytest.raises(ValueError, match="reconnect_delay"):
        BotConfig(reconnect_delay=-1.0)
    with pytest.raises(ValueError, match="view_distance"):
        BotConfig(view_distance=64)


def test_version_path_traversal_rejected():
    with pytest.raises(UnsupportedVersionError):
        load_version_json("../../etc", "passwd")
    with pytest.raises(UnsupportedVersionError):
        load_version_json("1.21.11", "../version")


@pytest.mark.asyncio
async def test_emitter_error_handler_no_infinite_recursion():
    emitter = EventEmitter()
    error_calls = 0

    async def bad_error_handler(*args):
        nonlocal error_calls
        error_calls += 1
        raise RuntimeError("error handler failed")

    def bad_handler():
        raise ValueError("boom")

    emitter.on("error", bad_error_handler)
    emitter.on("ping", bad_handler)
    emitter.emit("ping")
    await asyncio.sleep(0.05)
    assert error_calls == 1


@pytest.mark.asyncio
async def test_emitter_wait_for_nowait_cleanup_and_cancel_pending():
    emitter = EventEmitter()
    fut = emitter.wait_for_nowait("never")
    assert len(emitter._waiters.get("never", [])) == 1
    fut.cancel()
    await asyncio.sleep(0)
    assert "never" not in emitter._waiters

    started = asyncio.Event()

    async def slow():
        started.set()
        await asyncio.sleep(10)

    emitter.on("go", slow)
    emitter.emit("go")
    await started.wait()
    assert len(emitter._background_tasks) == 1
    await emitter.cancel_pending()
    assert len(emitter._background_tasks) == 0


def test_text_component_preserves_extra_and_strip_colors():
    comp = {"text": "", "extra": [{"text": "<Steve> "}, {"text": "Hello!"}]}
    assert component_to_text(comp) == "<Steve> Hello!"
    assert strip_colors("§aHello §l§cWorld§r!") == "Hello World!"


def test_nbt_hardening_bounds_depth_and_snbt_truncation():
    # EOF raises ValueError, not IndexError
    with pytest.raises(ValueError):
        read_tag(io.BytesIO(b""))

    # Negative array length rejected
    bad_arr = bytes([7, 0, 1, ord("a")]) + (-5).to_bytes(4, "big", signed=True)
    with pytest.raises(ValueError):
        read_compound(io.BytesIO(bad_arr))

    # Deep nesting rejected cleanly (not RecursionError)
    nested = bytes([TAG_Compound, 0, 1, ord("x")]) * 600 + b"\x00" * 600
    with pytest.raises(ValueError, match="depth"):
        read_compound(io.BytesIO(nested))

    # Truncated SNBT raises ValueError instead of looping forever
    with pytest.raises(ValueError):
        parse_snbt("{a:1")
    with pytest.raises(ValueError):
        parse_snbt("{a:[1,2")

    # Long array [L;...] parses as NBTLong
    parsed = parse_snbt("{ids:[L;1L,2L]}")
    assert isinstance(parsed["ids"][0], NBTLong)
    assert parsed["ids"] == [1, 2]

    # Roundtrip string
    raw = write_compound({"msg": "hello"})
    assert read_compound(io.BytesIO(raw)) == {"msg": "hello"}


def test_block_bedrock_hardness_and_can_dig_air():
    bedrock = Block(state_id=7, block_id=7, name="bedrock", position=BlockPos(0, 0, 0), hardness=-1.0, diggable=False)
    assert bedrock.hardness_seconds == float("inf")

    cave_air = Block(state_id=0, block_id=0, name="cave_air", position=BlockPos(0, 1, 0), hardness=0.0, diggable=False)
    assert cave_air.is_air is True

    lily = Block(state_id=111, block_id=111, name="waterlily", position=BlockPos(0, 2, 0))
    assert lily.is_fluid is False

    w = World(MagicMock(), "1.21.11")
    assert w.can_dig_block(cave_air) is False
    assert w.can_dig_block(bedrock) is False


@pytest.mark.asyncio
async def test_builder_navigate_out_of_reach_uses_valid_goal_near():
    bot = MagicMock()
    bot.game_mode = "creative"
    bot.creative.set_slot = AsyncMock()
    bot.equip = AsyncMock()
    bot.entity = MagicMock()
    bot.entity.position = Vec3(0, 64, 0)
    bot.world.block_at.return_value = None
    bot.actions.place_block = AsyncMock()
    bot.goto = AsyncMock(return_value=True)
    bot.emit = MagicMock()

    builder = BuilderModule(bot)
    plan = ConstructionPlan().add((20, 64, 20), "stone")
    ok = await builder.build(plan, reach=4.5, navigate=True, check_materials=False)
    assert ok is True
    assert bot.goto.call_count == 1
    goal_arg = bot.goto.call_args.args[0]
    assert isinstance(goal_arg, GoalNear)
    assert goal_arg.range == pytest.approx(3.5)


def test_actions_dig_face_opposes_view_direction():
    bot = MagicMock()
    bot.entity = SimpleNamespace(position=Vec3(0.5, 64.0, 0.5), eye_height=1.62)
    actions = ActionsModule(bot)
    # Block directly to the east (+X): visible face is west (face 4, normal -X).
    assert actions._dig_face(BlockPos(3, 65, 0)) == 4
    # Block directly to the north (-Z): visible face is south (face 3, normal +Z).
    assert actions._dig_face(BlockPos(0, 65, -3)) == 3


def test_bot_self_metadata_oxygen_and_health_heal_and_thunder():
    codec = SimpleNamespace(minecraft_version="1.21.11", protocol_version=774)
    bot = LeafishBot(BotConfig(), AuthSession("Steve", "00000000-0000-0000-0000-000000000001"), codec)  # type: ignore[arg-type]
    bot.entity_id = 42
    bot.entity = Player(id=42, uuid=bot.uuid, name="Steve")

    # Self entity metadata must update oxygen_level.
    bot._packet_entity_metadata({"entityId": 42, "metadata": [{"key": 1, "value": 180}]})
    assert bot.oxygen_level == 180

    # Healing must NOT emit entity_hurt; damage MUST emit entity_hurt.
    hurt_events = []
    bot.on("entity_hurt", lambda e: hurt_events.append(e))
    bot.vitals.health = 10.0
    bot._packet_update_health({"health": 15.0, "food": 20, "foodSaturation": 5.0})
    assert len(hurt_events) == 0
    bot._packet_update_health({"health": 12.0, "food": 20, "foodSaturation": 5.0})
    assert len(hurt_events) == 1

    # Thunder level 0.0 must clear thundering.
    bot._packet_game_state_change({"reason": "thunder_level_change", "gameMode": 1.0})
    assert bot.weather.thundering is True
    bot._packet_game_state_change({"reason": "thunder_level_change", "gameMode": 0.0})
    assert bot.weather.thundering is False


def test_entity_manager_preserves_tablist_on_spawn_and_destroy():
    em = EntityManager({122: "player"})
    uid = "00000000-0000-0000-0000-000000000099"
    em.players[uid] = Player(id=-1, uuid=uid, name="Alice")
    em.players[uid].latency = 42
    em.players[uid].game_mode = 0

    spawned = em.spawn({"entityId": 7, "type": 122, "objectUUID": uid, "x": 1, "y": 64, "z": 2})
    assert isinstance(spawned, Player)
    assert spawned.name == "Alice"
    assert spawned.latency == 42

    em.destroy([7])
    assert em.get(7) is None
    # Player still in tablist until player_remove arrives.
    assert uid in em.players


def test_plugin_circular_dependency_raises_plugin_error():
    bot = MagicMock()
    pm = PluginManager(bot)

    @plugin(name="a", dependencies=("b",))
    def plug_a(b):
        pass

    @plugin(name="b", dependencies=(plug_a,))
    def plug_b(b):
        pass

    with pytest.raises(PluginError, match="Circular"):
        pm.load(plug_b)
    assert pm.names == []


def test_vec3_format_and_coerce_goal_negative_coords():
    assert f"{Vec3(1.25, 2.5, 3.75):.1f}" == "(1.2, 2.5, 3.8)"
    g = coerce_goal(Vec3(-0.5, 64.0, -0.5))
    assert (g.x, g.y, g.z) == (-1, 64, -1)


def test_chunk_codec_palette_bounds_and_fast_values():
    # Oversized palette length rejected
    bad = bytes([4]) + encode_varint(1_000_000)
    with pytest.raises(ChunkDecodeError, match="palette length"):
        _decode_container_v2(_Reader(bad), 4096, 8, has_size_prefix=False)

    # PalettedContainer.values() matches get(i)
    pc = PalettedContainer(64, 4, [10, 20, 30, 40], [0x3210321032103210] * 4)
    assert pc.to_list() == [pc.get(i) for i in range(64)]


def test_framing_write_string_enforces_max_length():
    w = BufferWriter()
    with pytest.raises(PacketEncodeError):
        w.write_string("a" * 20, max_length=10)


def test_fishing_error_exported():
    assert FishingError is not None
