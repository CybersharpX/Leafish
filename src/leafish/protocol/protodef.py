"""Versioned Minecraft protocol codec backed by ``protolib``.

minecraft-data's ``protocol.json`` (ProtoDef schema) is loaded once per
Minecraft version and handed to :class:`protolib.Protocol`, which compiles
the container/array/switch/mapper/option/bitfield/bitflags and Minecraft
native types (``Slot``, ``entityMetadataLoop``, ``registryEntryHolder``,
``topBitSetTerminatedArray``, ``lpVec3`` ...) into serializers.

Nothing about packet IDs or layouts is hardcoded — everything comes from
the vendored per-version ``protocol.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import protolib

from ..exceptions import PacketDecodeError, PacketEncodeError, UnsupportedVersionError
from ..version import get_version_info, list_versions, load_version_json

_CODECS: dict[str, ProtocolCodec] = {}


def _packet_mappings(protocol_json: dict[str, Any], state: str, direction: str) -> dict[str, int]:
    """Extract the packet name -> id map from a state's ``packet`` type."""
    try:
        packet_type = protocol_json[state][direction]["types"]["packet"]
        fields = packet_type[1]
        mapper = fields[0]["type"]
        assert isinstance(mapper, list) and mapper[0] == "mapper"
        mappings = mapper[1]["mappings"]
    except (KeyError, IndexError, AssertionError, TypeError) as exc:
        raise PacketDecodeError(
            f"Cannot find packet mappings for {state}/{direction}"
        ) from exc

    name_to_id: dict[str, int] = {}
    for raw_key, name in mappings.items():
        try:
            name_to_id[name] = int(raw_key, 0)
        except ValueError:
            name_to_id[name] = int(raw_key)
    return name_to_id


@dataclass
class ProtocolCodec:
    """Encode/decode Minecraft packets for one protocol version."""

    minecraft_version: str
    protocol_version: int
    protocol: protolib.Protocol
    protocol_json: dict[str, Any]

    _name_maps: dict[tuple[str, str], dict[str, int]] | None = None

    # -- loading -----------------------------------------------------------

    @classmethod
    def for_version(cls, version: str = "latest") -> ProtocolCodec:
        """Return the (cached) codec for *version* (``"latest"`` allowed)."""
        from ..version import resolve_version

        resolved = resolve_version(version)
        if resolved in _CODECS:
            return _CODECS[resolved]
        info = get_version_info(resolved)
        protocol_json = load_version_json(info.minecraft_version, "protocol")
        codec = cls(
            minecraft_version=info.minecraft_version,
            protocol_version=info.protocol_version,
            protocol=protolib.Protocol(protocol_json),
            protocol_json=protocol_json,
        )
        _CODECS[resolved] = codec
        return codec

    # -- introspection ------------------------------------------------------

    def packet_names(self, state: str, direction: str) -> list[str]:
        """All packet names for ``(state, direction)`` (e.g. ``play/toClient``)."""
        return sorted(self._name_map(state, direction))

    def packet_id(self, state: str, direction: str, name: str) -> int:
        return self._name_map(state, direction)[name]

    def _name_map(self, state: str, direction: str) -> dict[str, int]:
        if self._name_maps is None:
            self._name_maps = {}
        key = (state, direction)
        if key not in self._name_maps:
            self._name_maps[key] = _packet_mappings(self.protocol_json, state, direction)
        return self._name_maps[key]

    # -- encode / decode -----------------------------------------------------

    def decode(self, state: str, direction: str, data: bytes) -> dict[str, Any]:
        """Decode a packet payload (id varint + fields, no length prefix).

        Returns ``{"name": <packet>, "params": {...}}``.
        """
        try:
            packet = self.protocol.parse_packet(state, direction, data)
        except Exception as exc:
            raise PacketDecodeError(
                f"Failed to decode {state}/{direction} packet: {exc}"
            ) from exc
        return {"name": packet.name, "params": packet.params}

    def encode(
        self,
        state: str,
        direction: str,
        name: str,
        params: dict[str, Any] | None = None,
    ) -> bytes:
        """Encode a packet; returns id varint + fields (no length prefix)."""
        if name not in self._name_map(state, direction):
            raise PacketEncodeError(
                f"Unknown {state}/{direction} packet '{name}' "
                f"(protocol {self.protocol_version})"
            )
        try:
            return self.protocol.serialize_packet(
                state, direction, name, params or {}
            )
        except Exception as exc:
            raise PacketEncodeError(
                f"Failed to encode {state}/{direction} packet '{name}': {exc}"
            ) from exc


def supported_versions() -> list[str]:
    """Minecraft versions with vendored protocol data."""
    return list_versions()


def default_version() -> str:
    """Newest vendored version, or raise."""
    versions = list_versions()
    if not versions:
        raise UnsupportedVersionError("No Minecraft version data is vendored")
    return versions[-1]
