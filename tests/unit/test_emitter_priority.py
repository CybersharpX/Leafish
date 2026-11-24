"""Tests for EventEmitter priority ordering and new API additions."""



from leafish.events.emitter import EventEmitter

# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


async def test_priority_higher_runs_first():
    em = EventEmitter()
    order = []

    em.on("evt", lambda: order.append("low"), priority=-1)
    em.on("evt", lambda: order.append("high"), priority=10)
    em.on("evt", lambda: order.append("normal"))  # priority=0

    em.emit("evt")
    assert order == ["high", "normal", "low"]


async def test_same_priority_fifo():
    em = EventEmitter()
    order = []

    em.on("evt", lambda: order.append(1))
    em.on("evt", lambda: order.append(2))
    em.on("evt", lambda: order.append(3))

    em.emit("evt")
    assert order == [1, 2, 3]


async def test_priority_decorator_form():
    em = EventEmitter()
    order = []

    @em.on("evt", priority=5)
    def high():
        order.append("high")

    @em.on("evt")
    def normal():
        order.append("normal")

    em.emit("evt")
    assert order == ["high", "normal"]


async def test_once_with_priority():
    em = EventEmitter()
    order = []

    em.once("evt", lambda: order.append("once-high"), priority=100)
    em.on("evt", lambda: order.append("on"))

    em.emit("evt")
    # once-high has priority 100 → runs before on (priority 0)
    assert order == ["once-high", "on"]

    order.clear()
    em.emit("evt")
    # once handler is gone; only on remains
    assert order == ["on"]


# ---------------------------------------------------------------------------
# off() removes by identity with new entry format
# ---------------------------------------------------------------------------


async def test_off_specific_handler():
    em = EventEmitter()
    calls = []

    def keep():
        calls.append("keep")

    def remove_me():
        calls.append("remove")

    em.on("evt", keep)
    em.on("evt", remove_me)
    em.off("evt", remove_me)
    em.emit("evt")
    assert calls == ["keep"]


async def test_off_all_handlers():
    em = EventEmitter()
    calls = []
    em.on("evt", lambda: calls.append(1))
    em.once("evt", lambda: calls.append(2))
    em.off("evt")
    em.emit("evt")
    assert calls == []


# ---------------------------------------------------------------------------
# listeners() returns in priority order
# ---------------------------------------------------------------------------


async def test_listeners_priority_order():
    em = EventEmitter()

    def a(): pass
    def b(): pass
    def c(): pass

    em.on("evt", a, priority=0)
    em.on("evt", b, priority=10)
    em.on("evt", c, priority=5)

    lst = em.listeners("evt")
    assert lst == [b, c, a]


# ---------------------------------------------------------------------------
# Error isolation still works with new entry format
# ---------------------------------------------------------------------------


async def test_error_isolation_with_priorities():
    em = EventEmitter()
    results = []

    em.on("error", lambda event, name, exc: results.append(("error", str(exc))))

    def bad():
        raise RuntimeError("boom")

    em.on("evt", bad, priority=1)
    em.on("evt", lambda: results.append("ok"))

    em.emit("evt")
    assert "ok" in results
    assert any(r[0] == "error" for r in results)
