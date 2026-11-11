"""Chat and commands module."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

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
