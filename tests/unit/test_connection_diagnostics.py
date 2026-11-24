"""Unit tests for connection diagnostics and metrics."""

from unittest.mock import MagicMock

from leafish.protocol.connection import Connection


def test_connection_diagnostics():
    codec = MagicMock()
    conn = Connection(codec, "127.0.0.1", 25565)

    # Initial state
    diag = conn.diagnostics()
    assert diag["connected"] is False
    assert diag["host"] == "127.0.0.1"
    assert diag["port"] == 25565
    assert diag["bytes_sent"] == 0
    assert diag["bytes_received"] == 0
    assert diag["packets_sent"] == 0
    assert diag["packets_received"] == 0

    # Simulate some traffic
    conn.bytes_sent = 1200
    conn.bytes_received = 8500
    conn.packets_sent = 15
    conn.packets_received = 42
    conn.latency_ms = 25.0

    diag2 = conn.diagnostics()
    assert diag2["bytes_sent"] == 1200
    assert diag2["bytes_received"] == 8500
    assert diag2["packets_sent"] == 15
    assert diag2["packets_received"] == 42
    assert diag2["latency_ms"] == 25.0
