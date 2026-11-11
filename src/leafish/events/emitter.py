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


class EventEmitter:
    """A small, safe event emitter supporting sync and async handlers.

    Handlers registered with :meth:`on` may be regular functions or coroutine
    functions. Coroutine handlers are scheduled as tasks; synchronous handlers
    run inline. A handler that raises never prevents other handlers from
    running — the exception is reported through the ``error`` event (when
    defined) and logged.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self._once_handlers: dict[str, list[Handler]] = {}
        self._waiters: dict[str, list[asyncio.Future]] = {}
        self._background_tasks: set[asyncio.Task] = set()

    # -- registration ------------------------------------------------------

    def on(self, event: str, handler: Handler | None = None) -> Any:
        """Register *handler* for *event*. Usable as a decorator.

        ``@emitter.on("spawn")`` or ``emitter.on("spawn", fn)``.
        """
        if handler is None:
            return lambda h: self.on(event, h)
        self._handlers.setdefault(event, []).append(handler)
        return handler

    def once(self, event: str, handler: Handler | None = None) -> Any:
        """Register a one-shot handler for *event*."""
        if handler is None:
            return lambda h: self.once(event, h)
        self._once_handlers.setdefault(event, []).append(handler)
        return handler

    def off(self, event: str, handler: Handler | None = None) -> None:
        """Remove *handler* from *event*, or all handlers when omitted."""
        if handler is None:
            self._handlers.pop(event, None)
            self._once_handlers.pop(event, None)
            return
        for table in (self._handlers, self._once_handlers):
            handlers = table.get(event)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def listeners(self, event: str) -> list[Handler]:
        """Return currently registered handlers for *event*."""
        return list(self._handlers.get(event, [])) + list(
            self._once_handlers.get(event, [])
        )

    # -- waiting -----------------------------------------------------------

    async def wait_for(
        self, event: str, timeout: float | None = None
    ) -> tuple[Any, ...]:
        """Wait until *event* is emitted; return its arguments.

        Raises :class:`asyncio.TimeoutError` on timeout.
        """
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._waiters.setdefault(event, []).append(fut)
        try:
            if timeout is not None:
                return await asyncio.wait_for(fut, timeout)
            return await fut
        finally:
            waiters = self._waiters.get(event)
            if waiters and fut in waiters:
                waiters.remove(fut)

    def wait_for_nowait(self, event: str) -> asyncio.Future:
        """Return a future that resolves with the next emission of *event*."""
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._waiters.setdefault(event, []).append(fut)
        return fut

    # -- dispatch ----------------------------------------------------------

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Dispatch *event* to all registered handlers and waiters.

        This method never raises: handler exceptions are routed to the
        ``error`` event (or logged if no error handler exists).
        """
        # Wake up waiters first.
        waiters = self._waiters.pop(event, [])
        for fut in waiters:
            if not fut.done():
                result = args if args else (kwargs,) if kwargs else ()
                fut.set_result(result if isinstance(result, tuple) else (result,))

        handlers = list(self._handlers.get(event, []))
        once = self._once_handlers.pop(event, [])
        handlers.extend(once)
        if not handlers:
            return

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
        waiters = self._waiters.pop(event, [])
        for fut in waiters:
            if not fut.done():
                fut.set_result(args if args else (kwargs,) if kwargs else ())

        handlers = list(self._handlers.get(event, []))
        once = self._once_handlers.pop(event, [])
        handlers.extend(once)

        for handler in handlers:
            try:
                result = handler(*args, **kwargs)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                self._report_error(event, handler, exc)

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
            except Exception as exc:
                self._report_error(event, handler, exc)

        task = loop.create_task(_runner())
        # Keep a reference so the task isn't garbage collected mid-flight.
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _report_error(self, event: str, handler: Handler, exc: BaseException) -> None:
        name = getattr(handler, "__name__", repr(handler))
        log.error("Event handler %r for '%s' raised: %r", name, event, exc)
        error_handlers = self._handlers.get("error", [])
        if error_handlers:
            for eh in error_handlers:
                try:
                    result = eh(event, name, exc)
                    if inspect.isawaitable(result):
                        self._schedule(result, "error", eh)
                except Exception:
                    log.exception("Error handler itself failed")
