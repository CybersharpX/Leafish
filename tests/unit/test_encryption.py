"""Unit tests for the AES/CFB8 encryption layer and server hash computation.

Vectors are taken from the Minecraft wiki and known-good test cases used by
other Minecraft client implementations.
"""

import hashlib

import pytest

from leafish.protocol.encryption import AesCfb8Cipher, EncryptionHandler

# ---------------------------------------------------------------------------
# AesCfb8Cipher
# ---------------------------------------------------------------------------


def test_cfb8_roundtrip():
    """Encrypt then decrypt should return the original data."""
    key = b"\x01" * 16
    cipher = AesCfb8Cipher(key, key)
    plaintext = b"Hello, Minecraft!"
    encrypted = cipher.encrypt(plaintext)
    assert encrypted != plaintext
    # Need a fresh cipher with the same key/IV to decrypt.
    cipher2 = AesCfb8Cipher(key, key)
    decrypted = cipher2.decrypt(encrypted)
    assert decrypted == plaintext


def test_cfb8_stream_continues():
    """Partial updates should produce the same result as a single update."""
    key = b"\xAB\xCD" * 8
    data = b"chunk1" + b"chunk2" + b"chunk3"

    # Single update.
    cipher_single = AesCfb8Cipher(key, key)
    expected = cipher_single.encrypt(data)

    # Three partial updates.
    cipher_partial = AesCfb8Cipher(key, key)
    out = cipher_partial.encrypt(b"chunk1")
    out += cipher_partial.encrypt(b"chunk2")
    out += cipher_partial.encrypt(b"chunk3")

    assert out == expected


def test_cfb8_key_must_be_16_bytes():
    with pytest.raises(ValueError, match="16 bytes"):
        AesCfb8Cipher(b"\x00" * 15, b"\x00" * 16)


def test_cfb8_independent_directions():
    """Encrypt and decrypt use independent cipher state (bidirectional streams)."""
    key = b"\xFF" * 16
    cipher = AesCfb8Cipher(key, key)
    # Encrypt some data.
    ct = cipher.encrypt(b"AAAA")
    # Then decrypt *different* data — the decryptor shouldn't share state.
    pt = cipher.decrypt(b"BBBB")
    # Encrypt and decrypt shouldn't return the same values when inputs differ.
    assert ct != pt


# ---------------------------------------------------------------------------
# EncryptionHandler
# ---------------------------------------------------------------------------


def test_encryption_handler_enable_and_passthrough():
    h = EncryptionHandler()
    assert not h.enabled

    secret = b"\x12\x34\x56\x78" * 4  # 16 bytes
    h.enable(secret)
    assert h.enabled

    plaintext = b"test payload"
    encrypted = h.encrypt_outgoing(plaintext)
    assert encrypted != plaintext

    # Decrypt with a fresh handler using the same secret.
    h2 = EncryptionHandler()
    h2.enable(secret)
    decrypted = h2.decrypt_incoming(encrypted)
    assert decrypted == plaintext


def test_encryption_handler_before_enable():
    """Before enable(), encrypt/decrypt are no-ops."""
    h = EncryptionHandler()
    data = b"raw"
    assert h.encrypt_outgoing(data) == data
    assert h.decrypt_incoming(data) == data


def test_encryption_handler_bad_secret():
    h = EncryptionHandler()
    with pytest.raises(ValueError, match="16 bytes"):
        h.enable(b"\x00" * 8)


# ---------------------------------------------------------------------------
# Server hash (Notch-signed SHA-1)
# ---------------------------------------------------------------------------


def _notch_hash_hex(data: bytes) -> str:
    """Reference Notch-signed SHA-1 hex digest (used by wiki.vg examples)."""
    digest = hashlib.sha1(data).digest()
    # Interpret digest as a signed big-endian 160-bit integer.
    value = int.from_bytes(digest, "big")
    if digest[0] & 0x80:
        value -= 1 << 160
    return format(value, "x")  # negative values already have a leading '-'


def test_notch_hash_positive():
    """'Notchian' server hash known vector from wiki.vg."""
    # server_id="Notch" gives a positive hex digest (no leading '-').
    result = _notch_hash_hex(b"Notch")
    assert result == "4ed1f46bbe04bc756bcb17c0c7ce3e4632f06a48"


def test_notch_hash_negative():
    # server_id="" (empty SHA-1 starts with 0x25...) — negative.
    result = _notch_hash_hex(b"")
    assert result == "-25c65c11a194b4f2cdaa40106a9fe76f5027f8f7"


def test_notch_hash_jeb():
    result = _notch_hash_hex(b"jeb_")
    assert result == "-7c9d5b0044c130109a5d7b5fb5c317c02b4e28c1"


def test_compute_server_hash_format():
    """_compute_server_hash returns Notch's signed lowercase hex digest."""
    from leafish.protocol.session import _compute_server_hash

    assert _compute_server_hash("Notch", b"", b"") == "4ed1f46bbe04bc756bcb17c0c7ce3e4632f06a48"
    assert _compute_server_hash("jeb_", b"", b"") == "-7c9d5b0044c130109a5d7b5fb5c317c02b4e28c1"
    assert _compute_server_hash("", b"", b"") == "-25c65c11a194b4f2cdaa40106a9fe76f5027f8f7"


# ---------------------------------------------------------------------------
# Verify that the encryption module exposes the expected public API.
# ---------------------------------------------------------------------------


def test_public_api():
    from leafish.protocol import encryption

    assert hasattr(encryption, "AesCfb8Cipher")
    assert hasattr(encryption, "EncryptionHandler")
