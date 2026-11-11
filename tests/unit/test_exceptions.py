
from leafish.exceptions import (
    AuthenticationError,
    ConnectionError,
    CraftingError,
    DiggingError,
    DisconnectError,
    InventoryError,
    LeafishError,
    MovementError,
    PacketDecodeError,
    PathfindingError,
    PluginError,
    ProtocolError,
    UnsupportedVersionError,
)


def test_all_derive_from_leafish_error():
    errors = [
        ConnectionError, AuthenticationError, ProtocolError,
        UnsupportedVersionError, PacketDecodeError, DisconnectError,
        MovementError, PathfindingError, InventoryError,
        DiggingError, CraftingError, PluginError,
    ]
    for cls in errors:
        assert issubclass(cls, LeafishError)


def test_disconnect_reason():
    err = DisconnectError("bye", reason="kicked")
    assert err.reason == "kicked"
    assert str(err) == "bye"
