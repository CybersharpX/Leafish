"""Leafish events sub-package.

Import the :class:`~leafish.events.emitter.EventEmitter` or use the
:mod:`~leafish.events.events` constants module for type-safe event names::

    from leafish.events import events as E

    @bot.on(E.SPAWN)
    async def on_spawn(): ...
"""

from . import events
from .emitter import EventEmitter

__all__ = ["EventEmitter", "events"]
