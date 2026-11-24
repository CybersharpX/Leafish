"""Unit tests for Bot and LeafishBot async context managers."""

from unittest.mock import AsyncMock, patch

import pytest

from leafish import Bot


@pytest.mark.asyncio
async def test_bot_async_context_manager():
    bot = Bot(host="localhost", port=25565, username="ContextBot")
    start_mock = AsyncMock()
    stop_mock = AsyncMock()

    with patch.object(bot, "start", start_mock), patch.object(bot, "stop", stop_mock):
        async with bot as b:
            assert b is bot
            start_mock.assert_awaited_once()
        stop_mock.assert_awaited_once()
