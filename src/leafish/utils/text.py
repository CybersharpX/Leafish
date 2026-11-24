"""Text helpers: protolib-NBT conversion and chat component flattening."""

from __future__ import annotations

import json
import re
from typing import Any

_COLOR_CODE_RE = re.compile(r"§[0-9A-FK-ORa-fk-or]")


def nbt_to_python(tag: Any) -> Any:
    """Convert a protolib NBT ``{"type","value"}`` structure to plain Python.

    Compounds become dicts of unwrapped values; scalars become Python
    primitives; lists keep their element type's ``value``.
    """
    if tag is None:
        return None
    if not isinstance(tag, dict) or "type" not in tag:
        return tag
    tag_type = tag.get("type")
    value = tag.get("value")
    if tag_type == "compound":
        return {k: nbt_to_python(v) for k, v in (value or {}).items()}
    if tag_type == "list":
        inner_type = (value or {}).get("type")
        items = (value or {}).get("value", [])
        if inner_type == "compound":
            return [nbt_to_python({"type": "compound", "value": i}) for i in items]
        return items
    return value


def component_to_text(component: Any) -> str:
    """Extract plain text from a Minecraft chat component.

    Accepts protolib-NBT chat components, plain dicts, JSON strings, or
    plain strings. Preserves both ``text`` and ``extra``/``with`` children.
    """
    if component is None:
        return ""
    if isinstance(component, str):
        # Might be JSON text or plain text.
        stripped = component.strip()
        if stripped.startswith(("{", "[", '"')):
            try:
                parsed = json.loads(stripped)
                if not isinstance(parsed, str) or parsed != component:
                    return component_to_text(parsed)
            except (json.JSONDecodeError, ValueError):
                pass
        return component
    if isinstance(component, (int, float)):
        return str(component)
    if isinstance(component, list):
        return "".join(component_to_text(c) for c in component)
    if isinstance(component, dict):
        # protolib NBT wrapper?
        if "type" in component and "value" in component and isinstance(component.get("type"), str):
            return component_to_text(nbt_to_python(component))
        # Chat component object: concatenate own text/translate + children/extra.
        parts: list[str] = []
        for key in ("text", "translate", "score", "selector", "keybind"):
            val = component.get(key)
            if isinstance(val, str):
                parts.append(val)
        for key in ("with", "extra"):
            if key in component:
                parts.append(component_to_text(component[key]))
        return "".join(parts)
    return str(component)


def strip_colors(text: str) -> str:
    """Remove Minecraft formatting codes (``§x``)."""
    return _COLOR_CODE_RE.sub("", text)
