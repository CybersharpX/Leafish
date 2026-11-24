"""Version-era compatibility helpers.

The protocol layer is data-driven, but gameplay code historically speaks
"modern" packet names and params (1.20.2+ shaped). This module adapts
outbound packets to the field layout of the negotiated protocol version
and describes era-specific wire differences (slot formats, chunk formats,
configuration state) that gameplay code needs to know about.

Nothing here hardcodes packet *ids* — all decisions are driven by the
vendored ``protocol.json`` field names.
"""

from __future__ import annotations

import time
from typing import Any

from .protodef import ProtocolCodec


def has_configuration_state(codec: ProtocolCodec) -> bool:
    """Whether the negotiated protocol has a ``configuration`` state.

    The configuration state was introduced in 1.20.2 (protocol 764); all
    earlier versions transition directly from login to play.
    """
    return codec.has_state("configuration")


def has_packet(codec: ProtocolCodec, name: str) -> bool:
    """Whether ``name`` exists in ``play/toServer``."""
    return codec.has_packet("play", "toServer", name)


def _fields(codec: ProtocolCodec, name: str) -> set[str] | None:
    fields = codec.packet_fields("play", "toServer", name)
    return set(fields) if fields is not None else None


def _pick(params: dict[str, Any], fields: set[str], defaults: dict[str, Any]) -> dict[str, Any]:
    """Build a params dict containing exactly the declared *fields*.

    Values come from *params* first, then *defaults*; fields with no
    value are filled with type-appropriate empties.
    """
    out: dict[str, Any] = {}
    for name in fields:
        if name in params:
            out[name] = params[name]
        elif name in defaults:
            out[name] = defaults[name]
        else:
            out[name] = _empty_for(name)
    return out


def _empty_for(name: str) -> Any:
    if name in ("signature", "checksum"):
        return None
    if name in ("acknowledged", "lastSeenMessages", "argumentSignatures"):
        return b"" if name == "acknowledged" else []
    return 0


# -- outbound chat -----------------------------------------------------------------


def adapt_chat(codec: ProtocolCodec, params: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Return ``(name, params)`` for sending a chat message, or ``None``.

    Handles the three wire eras: ``chat`` (<=1.18), signed
    ``chat_message`` (1.19-1.20.1), and the modern ``chat_message`` /
    ``chat_command`` split (1.20.2+).
    """
    is_command = str(params.get("message", "")).startswith("/")
    if has_packet(codec, "chat_command") and is_command:
        fields = _fields(codec, "chat_command")
        if fields is None:
            return None
        command = str(params["message"]).lstrip("/")
        defaults: dict[str, Any] = {
            "timestamp": int(time.time() * 1000),
            "salt": 0,
            "argumentSignatures": [],
            "signedPreview": False,
            "messageCount": 0,
            "acknowledged": b"",
        }
        merged = dict(defaults)
        merged["command"] = command
        merged.update({k: v for k, v in params.items() if k in fields})
        return "chat_command", _pick(merged, fields, defaults)

    if has_packet(codec, "chat_message"):
        fields = _fields(codec, "chat_message")
        if fields is None:
            return None
        defaults = {
            "timestamp": int(time.time() * 1000),
            "salt": 0,
            "signature": None,
            "signedPreview": False,
            "offset": 0,
            "acknowledged": b"",
            "checksum": 0,
        }
        merged = {"message": params.get("message", "")}
        merged.update({k: v for k, v in params.items() if k in fields})
        return "chat_message", _pick(merged, fields, defaults)

    if has_packet(codec, "chat"):
        # <= 1.18: a single message string (commands go through the same
        # packet with a leading '/').
        return "chat", {"message": params.get("message", "")}

    return None


def adapt_command(codec: ProtocolCodec, command: str) -> tuple[str, dict[str, Any]] | None:
    """Adapt :meth:`ChatModule.command` for the negotiated version."""
    return adapt_chat(codec, {"message": "/" + command.lstrip("/")})


# -- field-shape adapters -------------------------------------------------------------


def adapt_window_click(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``window_click`` params to the negotiated field layout."""
    fields = _fields(codec, "window_click")
    if fields is None:
        return params
    out: dict[str, Any] = {}
    mapping = {
        "windowId": "windowId",
        "stateId": "stateId",
        "slot": "slot",
        "mouseButton": "mouseButton",
        "mode": "mode",
        "action": "action",
        "item": "item",
        "changedSlots": "changedSlots",
        "cursorItem": "cursorItem",
    }
    for src, dst in mapping.items():
        if dst in fields and src in params:
            out[dst] = params[src]
    # Pre-1.17 layouts carry ``action`` and ``item`` instead of
    # ``stateId``/``changedSlots``/``cursorItem``.
    if "action" in fields and "action" not in out:
        out["action"] = 0
    if "item" in fields and "item" not in out:
        out["item"] = None
    for name in ("changedSlots", "cursorItem"):
        if name in fields and name not in out:
            out[name] = [] if name == "changedSlots" else None
    return out


def adapt_block_place(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``block_place`` (use item on block) params."""
    fields = _fields(codec, "block_place")
    if fields is None:
        return params
    hand = params.get("hand", 0)
    out: dict[str, Any] = {}
    if "hand" in fields:
        out["hand"] = hand
    if "heldItem" in fields:
        out["heldItem"] = params.get("heldItem", hand)
    for name in ("location", "direction", "cursorX", "cursorY", "cursorZ"):
        if name in fields and name in params:
            out[name] = params[name]
    if "insideBlock" in fields:
        out["insideBlock"] = bool(params.get("insideBlock", False))
    if "worldBorderHit" in fields:
        out["worldBorderHit"] = bool(params.get("worldBorderHit", False))
    if "sequence" in fields:
        out["sequence"] = int(params.get("sequence", 0))
    return out


def adapt_use_entity(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``use_entity`` params (26.1 moved position to ``location``)."""
    fields = _fields(codec, "use_entity")
    if fields is None:
        return params
    out: dict[str, Any] = {}
    for name in ("target", "mouse", "hand", "sneaking"):
        if name in fields and name in params:
            out[name] = params[name]
    if "location" in fields:
        loc = params.get("location")
        if loc is None:
            loc = {
                "x": params.get("x", 0.0),
                "y": params.get("y", 0.0),
                "z": params.get("z", 0.0),
            }
        out["location"] = loc
    else:
        for name in ("x", "y", "z"):
            if name in fields and name in params:
                out[name] = params[name]
    return out


def adapt_block_dig(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``block_dig`` params (``sequence`` added in 1.19)."""
    fields = _fields(codec, "block_dig")
    if fields is None:
        return params
    out = {k: v for k, v in params.items() if k in fields}
    if "sequence" in fields:
        out.setdefault("sequence", 0)
    return out


def adapt_use_item(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``use_item`` params."""
    fields = _fields(codec, "use_item")
    if fields is None:
        return params
    out = {k: v for k, v in params.items() if k in fields}
    if "sequence" in fields:
        out.setdefault("sequence", 0)
    if "rotation" in fields:
        out.setdefault("rotation", [0.0, 0.0])
    return out


def adapt_tab_complete(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``tab_complete`` params across its three layouts."""
    fields = _fields(codec, "tab_complete")
    if fields is None:
        return params
    text = params.get("text", "")
    if "transactionId" in fields:
        return {"transactionId": params.get("transactionId", 0), "text": text}
    if "assumeCommand" in fields:
        return {
            "text": text,
            "assumeCommand": bool(params.get("assumeCommand", False)),
            "lookedAtBlock": params.get("lookedAtBlock") or {
                "location": {"x": 0, "y": 0, "z": 0},
                "face": 1,
            },
        }
    # 1.8 layout.
    return {"text": text, "block": params.get("block") or {"x": 0, "y": 0, "z": 0}}


def adapt_resource_pack(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``resource_pack_receive`` params."""
    fields = _fields(codec, "resource_pack_receive")
    if fields is None:
        return params
    out: dict[str, Any] = {}
    if "uuid" in fields:
        out["uuid"] = params.get("uuid", "0" * 32)
    if "hash" in fields:
        out["hash"] = params.get("hash", "")
    out["result"] = params.get("result", 0)
    return out


def adapt_abilities(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``abilities`` params (speeds dropped in 1.16+)."""
    fields = _fields(codec, "abilities")
    if fields is None:
        return params
    out: dict[str, Any] = {}
    for name in ("flags", "flyingSpeed", "walkingSpeed"):
        if name in fields and name in params:
            out[name] = params[name]
        elif name in fields:
            out[name] = 0.05 if name == "flyingSpeed" else 0.1
    return out


def adapt_settings(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``settings``/client-information params."""
    fields = _fields(codec, "settings") or _fields(codec, "client_information")
    if fields is None:
        return params
    out: dict[str, Any] = {}
    for name, value in params.items():
        if name in fields:
            out[name] = value
    # Fill required fields with sane defaults.
    defaults = {
        "locale": "en_US",
        "viewDistance": 12,
        "chatFlags": 0,
        "chatColors": True,
        "skinParts": 0x7F,
        "mainHand": 1,
        "enableTextFiltering": False,
        "enableServerListing": True,
        "particleStatus": 0,
    }
    for name in fields:
        if name not in out:
            out[name] = defaults.get(name, 0)
    return out


def adapt_edit_book(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``edit_book`` params (rewritten in 1.18)."""
    fields = _fields(codec, "edit_book")
    if fields is None:
        return params
    if "pages" in fields:
        return {
            "hand": params.get("hand", 0),
            "pages": params.get("pages", []),
            "title": params.get("title"),
        }
    return {
        "new_book": params.get("new_book", False),
        "signing": bool(params.get("signing", False)),
        "hand": params.get("hand", 0),
    }


def adapt_held_item(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``held_item_slot`` params."""
    fields = _fields(codec, "held_item_slot")
    if fields is None:
        return params
    if "slot" in fields and "slotId" not in fields:
        return {"slot": params.get("slotId", params.get("slot", 0))}
    return {"slotId": params.get("slotId", params.get("slot", 0))}


def adapt_vehicle_move(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``vehicle_move`` params."""
    fields = _fields(codec, "vehicle_move")
    if fields is None:
        return params
    out = {k: v for k, v in params.items() if k in fields}
    if "onGround" in fields:
        out.setdefault("onGround", False)
    return out


def adapt_client_command(codec: ProtocolCodec, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt ``client_command`` params (``payload`` in 1.8 only)."""
    fields = _fields(codec, "client_command")
    if fields is None:
        return params
    if "payload" in fields:
        # 1.8 used a string enum payload; map common action ids.
        return {"payload": params.get("payload", params.get("actionId", "PERFORM_RESPAWN"))}
    return {"actionId": params.get("actionId", params.get("payload", 0))}


def adapt_movement(codec: ProtocolCodec, name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Adapt movement packets (``position``/``look``/``flying``/...).

    ``onGround`` is a plain bool up to 1.21.4 and a ``MovementFlags``
    bitflags dict from 1.21.5 on; callers pass a ``flags`` dict either
    way.
    """
    fields = _fields(codec, name)
    if fields is None:
        return params
    flags = params.get("flags")
    if isinstance(flags, dict):
        on_ground = bool(flags.get("onGround", params.get("onGround", False)))
    elif isinstance(flags, bool):
        on_ground = flags
    elif isinstance(flags, int):
        on_ground = bool(flags & 1)
    else:
        on_ground = bool(params.get("onGround", False))
    out: dict[str, Any] = {}
    for fname in ("x", "y", "z", "yaw", "pitch", "teleportId"):
        if fname in fields and fname in params:
            out[fname] = params[fname]
    if "onGround" in fields:
        out["onGround"] = on_ground
    if "flags" in fields:
        out["flags"] = flags if isinstance(flags, dict) else {
            "onGround": on_ground,
            "hasHorizontalCollision": False,
        }
    return out


# -- generic dispatcher ---------------------------------------------------------------


_ADAPTERS = {
    "window_click": adapt_window_click,
    "block_place": adapt_block_place,
    "use_entity": adapt_use_entity,
    "block_dig": adapt_block_dig,
    "use_item": adapt_use_item,
    "tab_complete": adapt_tab_complete,
    "resource_pack_receive": adapt_resource_pack,
    "abilities": adapt_abilities,
    "settings": adapt_settings,
    "client_information": adapt_settings,
    "edit_book": adapt_edit_book,
    "held_item_slot": adapt_held_item,
    "vehicle_move": adapt_vehicle_move,
    "client_command": adapt_client_command,
    "position": lambda c, p: adapt_movement(c, "position", p),
    "position_look": lambda c, p: adapt_movement(c, "position_look", p),
    "look": lambda c, p: adapt_movement(c, "look", p),
    "flying": lambda c, p: adapt_movement(c, "flying", p),
}


def adapt_send(
    codec: ProtocolCodec, name: str, params: dict[str, Any] | None
) -> tuple[str, dict[str, Any]] | None:
    """Adapt a ``play/toServer`` packet for the negotiated version.

    Returns ``(name, params)``, or ``None`` when the packet does not
    exist in this protocol version and should be skipped silently.
    """
    params = params or {}
    if name in ("chat_message", "chat"):
        adapted = adapt_chat(codec, params)
        if adapted is not None and adapted[0] == "chat_command":
            return adapted
        if adapted is not None:
            return adapted
        return None
    if name == "chat_command":
        adapted = adapt_command(codec, params.get("command", ""))
        return adapted if adapted is not None else None

    if not has_packet(codec, name):
        # Packet absent in this era (e.g. teleport_confirm pre-1.9,
        # transaction/close_window post-1.16, settings renamed, ...).
        return None

    adapter = _ADAPTERS.get(name)
    if adapter is not None:
        return name, adapter(codec, params)

    # Fallback: drop params that aren't declared fields.
    fields = _fields(codec, name)
    if fields is not None:
        return name, {k: v for k, v in params.items() if k in fields}
    return name, params


# -- slot formats -----------------------------------------------------------------------


def slot_format(codec: ProtocolCodec) -> str:
    """Classify the negotiated protocol's item slot wire format.

    Returns one of ``"legacy"`` (1.8-1.12: blockId/itemDamage/NBT),
    ``"flat"`` (1.13: itemId/NBT), ``"present"`` (1.15-1.20:
    present/itemId/NBT) or ``"components"`` (1.21+: itemCount/components).
    """
    for candidate in ("Slot", "slot"):
        packet_type = codec.protocol_json.get("types", {}).get(candidate)
        if not isinstance(packet_type, list):
            continue
        fields = [f.get("name") for f in packet_type[1] if isinstance(f, dict)]
        if "itemDamage" in fields or "blockId" in fields:
            return "legacy"
        if "itemDamage" in str(packet_type):
            return "legacy"
        if "present" in fields:
            return "present"
        if "components" in fields or "addedComponentCount" in fields:
            return "components"
        if "nbtData" in fields or "itemId" in fields:
            return "flat"
    return "components"


def slot_empty(codec: ProtocolCodec) -> dict[str, Any]:
    """An empty slot dict for the negotiated format."""
    fmt = slot_format(codec)
    if fmt == "legacy":
        return {"blockId": -1}
    if fmt == "flat":
        return {"itemId": -1}
    if fmt == "present":
        return {"present": False}
    return {"itemCount": 0}
