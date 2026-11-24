"""Asynchronous event emitter used by bots, worlds, windows and plugins."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

log = logging.getLogger("leafish.events")

Handler = Callable[..., Any]
F = TypeVar("F", bound=Handler)

# Internal sentinel: (priority, seq, handler).  Higher priority → runs first.
# ``seq`` breaks ties in insertion order (lower seq = registered earlier).
_Entry = tuple[int, int, Handler]


class EventEmitter:
    """A small, safe event emitter supporting sync and async handlers.

    Handlers registered with :meth:`on` may be regular functions or coroutine
    functions. Coroutine handlers are scheduled as tasks; synchronous handlers
    run inline. A handler that raises never prevents other handlers from
    running — the exception is reported through the ``error`` event (when
    defined) and logged.

    Priority
    --------
    Both :meth:`on` and :meth:`once` accept an optional *priority* integer
    (default ``0``).  Handlers with a **higher** priority run **before**
    handlers with a lower priority.  Handlers at the same priority level run
    in registration order (FIFO).
    """

    def __init__(self) -> None:
        # Maps event → list of _Entry sorted descending by (priority, -seq).
        self._handlers: dict[str, list[_Entry]] = {}
        self._once_handlers: dict[str, list[_Entry]] = {}
        self._waiters: dict[str, list[asyncio.Future[Any]]] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._seq: int = 0  # global monotonic counter for FIFO ordering

    # -- registration -------------------------------------------------------

    def on(self, event: str, handler: Handler | None = None, *, priority: int = 0) -> Any:
        """Register *handler* for *event*. Usable as a decorator."""
        if handler is None:
            return lambda h: self.on(event, h, priority=priority)
        self._insert(self._handlers, event, handler, priority)
        return handler

    def once(self, event: str, handler: Handler | None = None, *, priority: int = 0) -> Any:
        """Register a one-shot handler for *event*."""
        if handler is None:
            return lambda h: self.once(event, h, priority=priority)
        self._insert(self._once_handlers, event, handler, priority)
        return handler

    def off(self, event: str, handler: Handler | None = None) -> None:
        """Remove *handler* from *event*, or all handlers when omitted."""
        if handler is None:
            self._handlers.pop(event, None)
            self._once_handlers.pop(event, None)
            return
        for table in (self._handlers, self._once_handlers):
            entries = table.get(event)
            if entries:
                remaining = [e for e in entries if e[2] is not handler]
                if remaining:
                    table[event] = remaining
                else:
                    table.pop(event, None)

    def listeners(self, event: str) -> list[Handler]:
        """Return currently registered handlers for *event* (priority order)."""
        entries = list(self._handlers.get(event, ())) + list(self._once_handlers.get(event, ()))
        entries.sort(key=lambda e: (-e[0], e[1]))
        return [e[2] for e in entries]

    # -- waiting ------------------------------------------------------------

    async def wait_for(
        self, event: str, timeout: float | None = None
    ) -> tuple[Any, ...]:
        """Wait until *event* is emitted; return its arguments.

        Raises :class:`asyncio.TimeoutError` on timeout.
        """
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._waiters.setdefault(event, []).append(fut)
        try:
            if timeout is not None:
                return await asyncio.wait_for(fut, timeout)
            return await fut
        finally:
            self._remove_waiter(event, fut)

    def wait_for_nowait(self, event: str) -> asyncio.Future[Any]:
        """Return a future that resolves with the next emission of *event*."""
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._waiters.setdefault(event, []).append(fut)
        fut.add_done_callback(lambda f: self._remove_waiter(event, f))
        return fut

    def _remove_waiter(self, event: str, fut: asyncio.Future[Any]) -> None:
        waiters = self._waiters.get(event)
        if waiters:
            try:
                waiters.remove(fut)
            except ValueError:
                pass
            if not waiters:
                self._waiters.pop(event, None)

    async def cancel_pending(self) -> None:
        """Cancel all pending waiters and in-flight async handler tasks."""
        for waiters in list(self._waiters.values()):
            for fut in waiters:
                if not fut.done():
                    fut.cancel()
        self._waiters.clear()
        tasks = list(self._background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._background_tasks.clear()

    # -- dispatch -----------------------------------------------------------

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Dispatch *event* to all registered handlers and waiters.

        This method never raises: handler exceptions are routed to the
        ``error`` event (or logged if no error handler exists).
        """
        # Wake up waiters first.
        waiters = self._waiters.pop(event, None)
        if waiters:
            result_val = args if args else (kwargs,) if kwargs else ()
            resolved = result_val if isinstance(result_val, tuple) else (result_val,)
            for fut in waiters:
                if not fut.done():
                    fut.set_result(resolved)

        entries = self._handlers.get(event)
        once_entries = self._once_handlers.pop(event, None)
        if not entries and not once_entries:
            return
        if once_entries:
            combined = (list(entries) if entries else []) + once_entries
            combined.sort(key=lambda e: (-e[0], e[1]))
            handlers = [e[2] for e in combined]
        else:
            assert entries is not None
            handlers = [e[2] for e in entries]

        for handler in handlers:
            try:
                result = handler(*args, **kwargs)
            except Exception as exc:
                self._report_error(event, handler, exc)
                continue
            if inspect.isawaitable(result):
                self._schedule(result, event, handler)

    async def emit_async(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Like :meth:`emit` but awaits async handlers before returning."""
        waiters = self._waiters.pop(event, None)
        if waiters:
            result_val = args if args else (kwargs,) if kwargs else ()
            for fut in waiters:
                if not fut.done():
                    fut.set_result(result_val)

        entries = self._handlers.get(event)
        once_entries = self._once_handlers.pop(event, None)
        if not entries and not once_entries:
            return
        if once_entries:
            combined = (list(entries) if entries else []) + once_entries
            combined.sort(key=lambda e: (-e[0], e[1]))
            handlers = [e[2] for e in combined]
        else:
            assert entries is not None
            handlers = [e[2] for e in entries]

        for handler in handlers:
            try:
                result = handler(*args, **kwargs)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                self._report_error(event, handler, exc)

    # -- internals ----------------------------------------------------------

    def _insert(
        self,
        table: dict[str, list[_Entry]],
        event: str,
        handler: Handler,
        priority: int,
    ) -> None:
        """Insert *handler* into *table[event]* maintaining priority order."""
        seq = self._seq
        self._seq += 1
        entry: _Entry = (priority, seq, handler)
        lst = table.setdefault(event, [])
        idx = len(lst)
        for i, (p, s, _) in enumerate(lst):
            if priority > p or (priority == p and seq < s):
                idx = i
                break
        lst.insert(idx, entry)

    def _schedule(self, coro: Coroutine[Any, Any, Any], event: str, handler: Handler) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            self._report_error(event, handler, RuntimeError("no running event loop"))
            return

        async def _runner() -> None:
            try:
                await coro
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._report_error(event, handler, exc)

        task = loop.create_task(_runner())
        # Keep a reference so the task isn't garbage collected mid-flight.
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _report_error(self, event: str, handler: Handler, exc: BaseException) -> None:
        name = getattr(handler, "__name__", repr(handler))
        log.error("Event handler %r for '%s' raised: %r", name, event, exc)
        # Never recurse when an "error" handler itself fails.
        if event == "error":
            return
        error_handlers = [e[2] for e in self._handlers.get("error", ())]
        if error_handlers:
            for eh in error_handlers:
                try:
                    result = eh(event, name, exc)
                    if inspect.isawaitable(result):
                        self._schedule(result, "error", eh)
                except Exception:
                    log.exception("Error handler itself failed")
