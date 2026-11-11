"""Client-facing protocol helpers: tab-completion, resource packs,
signs, books, command blocks and feature detection."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ..utils.vectors import BlockPos, Vec3

if TYPE_CHECKING:
    from ..bot import LeafishBot

log = logging.getLogger("leafish.client")

_NIL_UUID = "00000000-0000-0000-0000-000000000000"

#: Vanilla resource-pack response statuses (varint).
RESOURCE_PACK_ACCEPTED = 3
RESOURCE_PACK_DOWNLOADED = 4
RESOURCE_PACK_SUCCESS = 0
RESOURCE_PACK_DECLINED = 1


class ClientModule:
    """Miscellaneous clientbound/serverbound protocol interactions."""

    def __init__(self, bot: LeafishBot) -> None:
        self.bot = bot
        self._tab_transaction = 0
        self._last_explosion: dict[str, Any] | None = None

    # -- tab completion ---------------------------------------------------------

    async def tab_complete(
        self,
        text: str,
        assume_command: bool = False,
        timeout: float = 5.0,
    ) -> list[str]:
        """Request tab-completion for *text*; returns matching strings.

        *assume_command* prefixes the text with ``/`` when it doesn't
        already start with one (chat vs command context).
        """
        if assume_command and not text.startswith("/"):
            text = "/" + text
        self._tab_transaction = (self._tab_transaction + 1) & 0x7FFFFFFF
        tid = self._tab_transaction
        await self.bot._send_play(
            "tab_complete",
            {"transactionId": tid, "text": text},
        )
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()

        def on_response(params: dict[str, Any]) -> None:
            if fut.done() or params.get("transactionId") != tid:
                return
            matches = params.get("matches") or []
            fut.set_result([m.get("match", "") for m in matches])

        self.bot.on("tab_complete_response", on_response)
        try:
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError:
            return []
        finally:
            self.bot.off("tab_complete_response", on_response)

    # -- resource packs -----------------------------------------------------------

    async def accept_resource_pack(self) -> None:
        """Accept the server's resource pack request."""
        await self._resource_pack_response(RESOURCE_PACK_ACCEPTED)
        # Vanilla clients follow up with DOWNLOADED then SUCCESS; a bot has
        # no pack to download, so report success directly as well.
        await self._resource_pack_response(RESOURCE_PACK_SUCCESS)

    async def deny_resource_pack(self) -> None:
        """Decline the server's resource pack request."""
        await self._resource_pack_response(RESOURCE_PACK_DECLINED)

    async def _resource_pack_response(self, result: int) -> None:
        await self.bot._send_play(
            "resource_pack_receive",
            {"uuid": _NIL_UUID, "result": result},
        )
        self.bot.emit("resource_pack_response", result)

    # -- signs ----------------------------------------------------------------------

    async def update_sign(
        self,
        block,
        text,
        back: bool = False,
        timeout: float = 5.0,
    ) -> bool:
        """Write *text* (str or list of 4 lines) onto a sign.

        Right-clicks the sign, waits for the server's ``open_sign_entity``
        packet, then sends ``update_sign``. Returns ``True`` on success.
        """
        lines = self._sign_lines(text)
        pos = self._resolve_pos(block)
        # Wait for the open-sign packet, then answer it.
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()

        def on_open(params: dict[str, Any]) -> None:
            loc = params.get("location")
            bx = getattr(loc, "x", None)
            if bx is None and isinstance(loc, dict):
                bx = loc.get("x")
            if fut.done():
                return
            fut.set_result(params)

        self.bot.on("open_sign_entity", on_open)
        try:
            await self.bot.interact_block(block)
            params = await asyncio.wait_for(fut, timeout)
        except TimeoutError:
            return False
        finally:
            self.bot.off("open_sign_entity", on_open)
        is_front = bool(params.get("isFrontText", not back))
        await self.bot._send_play(
            "update_sign",
            {
                "location": {"x": pos.x, "y": pos.y, "z": pos.z},
                "isFrontText": is_front,
                "text1": lines[0],
                "text2": lines[1],
                "text3": lines[2],
                "text4": lines[3],
            },
        )
        self.bot.emit("sign_update", pos, lines)
        return True

    @staticmethod
    def _sign_lines(text) -> list[str]:
        if isinstance(text, str):
            return [text, "", "", ""]
        lines = [str(t)[:384] for t in list(text)[:4]]
        return [*lines, "", "", "", ""][:4]

    @staticmethod
    def _resolve_pos(block) -> BlockPos:
        pos = getattr(block, "position", block)
        if isinstance(pos, Vec3):
            return pos.floor()
        if isinstance(pos, tuple):
            return BlockPos(*pos)
        return pos

    # -- books ------------------------------------------------------------------------

    async def write_book(self, hand: int, pages: list[str],
                         title: str | None = None) -> None:
        """Write *pages* into the writable book held in *hand*.

        *hand* is 0 (main) or 1 (off). The book must already be equipped.
        """
        await self.bot._send_play(
            "edit_book",
            {
                "hand": hand,
                "pages": list(pages),
                "title": title,
            },
        )
        self.bot.emit("book_write", hand)

    # -- command blocks ---------------------------------------------------------------

    async def set_command_block(
        self,
        pos,
        command: str,
        *,
        mode: int = 0,
        flags: int = 0,
    ) -> None:
        """Update a command block at *pos*.

        *mode*: 0=chain, 1=repeating, 2=normal. *flags* bitfield:
        0x01 track output, 0x02 conditional.
        """
        p = self._resolve_pos(pos)
        await self.bot._send_play(
            "update_command_block",
            {
                "location": {"x": p.x, "y": p.y, "z": p.z},
                "command": command,
                "mode": mode,
                "flags": flags,
            },
        )
        self.bot.emit("command_block_update", p, command)

    # -- held item / misc ----------------------------------------------------------------

    async def update_held_item(self) -> None:
        """Re-send the current hotbar selection to the server."""
        await self.bot._send_play(
            "held_item_slot", {"slotId": self.bot.inventory.held_slot}
        )

    def support_feature(self, name: str) -> bool:
        """Whether the server advertised feature flag *name*.

        Returns ``True`` for unknown names (permissive default matching
        vanilla behaviour for optional features).
        """
        flags = getattr(self.bot, "feature_flags", None)
        if flags is None:
            return True
        return name in flags

    def get_explosion_damages(
        self,
        entity=None,
        position=None,
        radius: float = 0.0,
        raw_damages: bool = False,
    ) -> dict:
        """Compute explosion damage exposure for *entity* (defaults to the
        bot) from the last ``explosion`` packet.

        Returns ``{"damage": float, "knockback": Vec3}`` scaled by
        distance/ray exposure, or raw exposure values when *raw_damages*.
        """
        last = self._last_explosion
        if last is None:
            return {"damage": 0.0, "knockback": Vec3(0, 0, 0)}
        center = position or last.get("center") or Vec3(0, 0, 0)
        ent = entity if entity is not None else self.bot.entity
        if ent is None:
            return {"damage": 0.0, "knockback": Vec3(0, 0, 0)}
        delta = ent.position - center
        dist = delta.length
        r = radius or float(last.get("radius", 1.0))
        if dist >= r or r <= 0:
            exposure = 0.0
        else:
            exposure = 1.0 - dist / r
            # Ray-exposure: average over eye->center samples is
            # approximated by 1.0; a full implementation samples blocks.
            exposure *= 1.0
        damage = exposure * exposure * 7.0 * (8.0 / max(dist, 1.0)) * r + 1.0
        kb = delta.normalized * exposure * 1.0 if dist > 0 else Vec3(0, 0, 0)
        if raw_damages:
            return {"exposure": exposure, "distance": dist}
        return {"damage": damage, "knockback": kb}

    def record_explosion(self, params: dict[str, Any]) -> None:
        """Called by the bot's explosion packet handler."""
        center = params.get("center") or params.get("position")
        if isinstance(center, dict):
            center = Vec3(center.get("x", 0), center.get("y", 0), center.get("z", 0))
        self._last_explosion = {
            "center": center,
            "radius": float(params.get("radius", params.get("power", 0)) or 0),
            "params": params,
        }
