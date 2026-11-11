"""Text helpers: protolib-NBT conversion and chat component flattening."""

from __future__ import annotations

import json
from typing import Any


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
    plain strings.
    """
    if component is None:
        return ""
    if isinstance(component, str):
        # Might be JSON text or plain text.
        try:
            parsed = json.loads(component)
            return component_to_text(parsed)
        except (json.JSONDecodeError, ValueError):
            return component
    if isinstance(component, (int, float)):
        return str(component)
    if isinstance(component, list):
        return "".join(component_to_text(c) for c in component)
    if isinstance(component, dict):
        # protolib NBT wrapper?
        if "type" in component and "value" in component and isinstance(component.get("type"), str):
            return component_to_text(nbt_to_python(component))
        if "text" in component:
            return str(component.get("text", ""))
        # Chat component object: concatenate children/extra.
        parts = []
        for key in ("text", "translate", "score", "selector", "keybind"):
            if key in component and isinstance(component[key], str):
                parts.append(component[key])
        for key in ("extra", "with"):
            if key in component:
                parts.append(component_to_text(component[key]))
        return "".join(parts)
    return str(component)


def strip_colors(text: str) -> str:
    """Remove Minecraft formatting codes (§x)."""
    return "".join(c for c in text if c != "§")
