"""Chat and commands module."""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..bot import LeafishBot


class ChatModule:
    """Send chat messages and commands."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._message_count = 0
        self._salt = int(time.time() * 1000) & 0xFFFFFFFF

    async def chat(self, message: str) -> None:
        """Send a plain chat message."""
        if not message:
            return
        if message.startswith("/"):
            await self.command(message[1:])
            return
        self._message_count += 1
        await self.bot._send_play(
            "chat_message",
            {
                "message": message,
                "timestamp": int(time.time() * 1000),
                "salt": self._salt,
                "signature": None,
                "offset": 0,
                "acknowledged": b"\x00" * 3,
                "checksum": 0,
            },
        )

    async def command(self, command: str) -> None:
        """Send a slash command (without the leading '/')."""
        await self.bot._send_play(
            "chat_command", {"command": command.lstrip("/")}
        )

    async def whisper(self, recipient: str, message: str) -> None:
        """Send a private message via the /msg command."""
        await self.command(f"msg {recipient} {message}")

    # -- chat patterns -------------------------------------------------------------

    def add_chat_pattern(
        self,
        name: str,
        pattern: str | re.Pattern[str],
        chat_type: str = "chat",
    ) -> None:
        """Register a regex *pattern* that emits ``chat:<name>`` events.

        When an incoming message of *chat_type* matches, the bot emits
        ``chat:<name>`` with ``(username, message, match)``.
        """
        self.bot.chat_patterns[name] = {
            "pattern": re.compile(pattern),
            "chatType": chat_type,
        }

    def add_chat_pattern_set(
        self,
        name: str,
        patterns: list[str | re.Pattern[str]],
        chat_type: str = "chat",
    ) -> None:
        """Register several patterns under one ``chat:<name>`` event."""
        self.bot.chat_patterns[name] = {
            "patterns": [re.compile(p) for p in patterns],
            "chatType": chat_type,
        }

    def remove_chat_pattern(self, name: str) -> None:
        """Remove a previously registered chat pattern."""
        self.bot.chat_patterns.pop(name, None)

    # -- awaiting messages ------------------------------------------------------------

    async def await_message(
        self,
        pattern: str | re.Pattern[str] | None = None,
        *,
        timeout: float = 30.0,
        chat_type: str = "chat",
    ) -> tuple[str | None, str, Any]:
        """Wait for an incoming chat message matching *pattern*.

        Returns ``(username, message, match)`` where *match* is the regex
        match object (or ``None`` when no pattern was given).
        Raises :class:`asyncio.TimeoutError` on timeout.
        """
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()

        def check(username, message, *rest):
            if fut.done():
                return
            if regex is not None:
                m = regex.search(message or "")
                if m is None:
                    return
                fut.set_result((username, message, m))
            else:
                fut.set_result((username, message, None))

        self.bot.on(chat_type, check)
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self.bot.off(chat_type, check)
