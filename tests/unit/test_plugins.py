"""Plugin loader tests."""

from typing import Any, cast

import pytest

from leafish.events.emitter import EventEmitter
from leafish.exceptions import PluginError
from leafish.plugins import PluginManager


class _Bot:
    def __init__(self) -> None:
        self.emitter = EventEmitter()
        self.loaded: list[str] = []

    def emit(self, event, *args, **kwargs) -> None:
        self.emitter.emit(event, *args, **kwargs)

    def on(self, event, handler=None):
        return self.emitter.on(event, handler)


def _manager() -> tuple[PluginManager, _Bot]:
    bot = _Bot()
    return PluginManager(cast(Any, bot)), bot


def test_load_callable_plugin():
    pm, bot = _manager()

    def plugin(b):
        b.loaded.append("hi")

    name = pm.load(plugin)
    assert name == "plugin"
    assert bot.loaded == ["hi"]
    assert pm.plugins == ["plugin"]


def test_load_object_plugin_with_inject():
    pm, bot = _manager()

    class P:
        name = "obj-plugin"

        def inject(self, b):
            b.loaded.append("injected")

        def unload(self, b):
            b.loaded.append("unloaded")

    pm.load(P())
    assert bot.loaded == ["injected"]
    assert pm.unload("obj-plugin") is True
    assert bot.loaded == ["injected", "unloaded"]
    assert pm.plugins == []


def test_load_invalid_plugin_raises():
    pm, _ = _manager()
    with pytest.raises(PluginError):
        pm.load(object())


def test_plugin_error_wrapped():
    pm, _ = _manager()

    def bad(b):
        raise RuntimeError("boom")

    with pytest.raises(PluginError):
        pm.load(bad)
    assert pm.plugins == []


def test_plugin_loaded_event():
    pm, bot = _manager()
    seen = []
    bot.on("plugin_loaded", lambda n: seen.append(n))
    pm.load(lambda b: None, name="evt-plugin")
    assert seen == ["evt-plugin"]
