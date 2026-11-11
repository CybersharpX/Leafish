import asyncio

import pytest

from leafish.events.emitter import EventEmitter


async def test_on_and_emit_sync():
    em = EventEmitter()
    seen = []
    em.on("chat", lambda msg: seen.append(msg))
    em.emit("chat", "hello")
    assert seen == ["hello"]


async def test_async_handler_is_scheduled():
    em = EventEmitter()
    seen = []

    async def handler(msg):
        await asyncio.sleep(0)
        seen.append(msg)

    em.on("chat", handler)
    em.emit("chat", "hi")
    await asyncio.sleep(0.01)
    assert seen == ["hi"]


async def test_handler_exception_isolated():
    em = EventEmitter()
    errors = []
    em.on("error", lambda event, name, exc: errors.append((event, name)))

    def bad():
        raise ValueError("boom")

    def good():
        errors.append(("good", ""))

    em.on("chat", bad)
    em.on("chat", good)
    em.emit("chat")
    assert ("good", "") in errors
    assert errors[0][0] == "chat"  # error event fired first or after — both present
    assert any(e[0] == "chat" for e in errors)


async def test_off_and_once():
    em = EventEmitter()
    calls = []
    em.on("x", lambda: calls.append("on"))
    em.once("x", lambda: calls.append("once"))
    em.emit("x")
    em.emit("x")
    assert calls == ["once", "on", "on"] or calls.count("once") == 1
    em.off("x")
    em.emit("x")
    assert calls.count("on") == 2


async def test_wait_for():
    em = EventEmitter()

    async def emit_later():
        await asyncio.sleep(0.01)
        em.emit("spawn", 1, 2)

    task = asyncio.create_task(emit_later())
    result = await em.wait_for("spawn", timeout=1)
    await task
    assert result == (1, 2)


async def test_wait_for_timeout():
    em = EventEmitter()
    with pytest.raises(asyncio.TimeoutError):
        await em.wait_for("never", timeout=0.01)


async def test_decorator_usage():
    em = EventEmitter()

    @em.on("chat")
    async def on_chat(msg):
        return msg

    assert on_chat is not None
    em.emit("chat", "yo")
    await asyncio.sleep(0)
