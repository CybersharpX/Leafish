"""Tests for the high-level Bot wrapper and BotConfig additions."""

import pytest

from leafish import Bot
from leafish.config import BotConfig, _default_token_path

# ---------------------------------------------------------------------------
# BotConfig
# ---------------------------------------------------------------------------


def test_default_token_path_is_callable():
    p1 = _default_token_path()
    p2 = _default_token_path()
    assert p1 == p2
    assert p1.name == "tokens.json"


def test_botconfig_token_path_per_instance():
    """Each BotConfig instance gets its own Path object (not shared)."""
    c1 = BotConfig()
    c2 = BotConfig()
    # Should be equal paths but independent objects.
    assert c1.token_cache_path == c2.token_cache_path
    # Mutating one should not affect the other.
    c1.token_cache_path = c1.token_cache_path / "sub"
    assert c2.token_cache_path.name == "tokens.json"


def test_botconfig_auto_reconnect_defaults():
    c = BotConfig()
    assert c.auto_reconnect is False
    assert c.reconnect_delay == 5.0


def test_botconfig_auto_reconnect_set():
    c = BotConfig(auto_reconnect=True, reconnect_delay=10.0)
    assert c.auto_reconnect is True
    assert c.reconnect_delay == 10.0


# ---------------------------------------------------------------------------
# Bot wrapper (pre-start)
# ---------------------------------------------------------------------------


def test_bot_repr_before_start():
    bot = Bot(host="mc.example.com", port=25565)
    r = repr(bot)
    assert "mc.example.com" in r
    assert "not started" in r


def test_bot_attr_before_start_raises():
    bot = Bot()
    with pytest.raises(AttributeError, match=r"await bot\.start"):
        _ = bot.chat


def test_bot_on_decorator_buffers_before_start():
    """Handlers registered before start() are buffered, not lost."""
    bot = Bot()
    recorded = []

    @bot.on("spawn")
    def on_spawn():
        recorded.append("spawn")

    # Handler should be in the pending queue.
    assert len(bot._pending_handlers) == 1
    assert bot._pending_handlers[0][0] == "spawn"
    assert bot._pending_handlers[0][1] is on_spawn


def test_bot_once_buffers_before_start():
    bot = Bot()

    @bot.once("connect")
    def on_connect():
        pass

    assert len(bot._pending_handlers) == 1
    event, _fn, is_once = bot._pending_handlers[0]
    assert event == "connect"
    assert is_once is True


def test_bot_on_with_explicit_handler_before_start():
    bot = Bot()
    fn = lambda: None  # noqa: E731
    bot.on("chat", fn)
    assert len(bot._pending_handlers) == 1
    assert bot._pending_handlers[0][1] is fn
