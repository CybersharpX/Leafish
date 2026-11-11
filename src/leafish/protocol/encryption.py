"""AES/CFB8 stream encryption used by Minecraft's encryption handshake."""

from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class AesCfb8Cipher:
    """AES/CFB8 cipher matching Minecraft's shared-secret encryption.

    The same key/IV pair is used in both directions (CFB8 with a zero IV for
    the client->server direction is handled by the caller passing the right
    IV; Minecraft uses the shared secret as key and an IV derived per stream).
    """

    def __init__(self, key: bytes, iv: bytes) -> None:
        if len(key) != 16:
            raise ValueError("AES key must be 16 bytes")
        # Minecraft uses AES in CFB8 mode (8-bit segments).
        self._encryptor = Cipher(algorithms.AES(key), modes.CFB8(iv)).encryptor()
        self._decryptor = Cipher(algorithms.AES(key), modes.CFB8(iv)).decryptor()

    def encrypt(self, data: bytes) -> bytes:
        return self._encryptor.update(data) + self._encryptor.finalize()

    def decrypt(self, data: bytes) -> bytes:
        return self._decryptor.update(data) + self._decryptor.finalize()


def make_cipher(shared_secret: bytes, use_second_iv: bool = False) -> AesCfb8Cipher:
    """Build the standard Minecraft AES/CFB8 cipher from a shared secret.

    Minecraft derives key = SHA-1(secret)[0:16] and two IVs from the digest;
    client->server uses the first IV, server->client the second.
    """
    import hashlib

    digest = hashlib.sha1(shared_secret).digest()
    key = digest[:16]
    iv = digest[4:20] if not use_second_iv else digest[8:24]
    # Vanilla actually uses: key = digest[0:16], iv1 = digest[4:20], iv2 = digest[8:24]
    return AesCfb8Cipher(key, iv)


def derive_key_iv(shared_secret: bytes) -> tuple[bytes, bytes, bytes]:
    """Return ``(key, client_iv, server_iv)`` per the Minecraft spec."""
    import hashlib

    digest = hashlib.sha1(shared_secret).digest()
    return digest[:16], digest[4:20], digest[8:24]


class EncryptionHandler:
    """Bidirectional encryption state for a connection."""

    def __init__(self) -> None:
        self.enabled = False
        self._to_server: AesCfb8Cipher | None = None
        self._to_client: AesCfb8Cipher | None = None

    def enable(self, shared_secret: bytes) -> None:
        key, client_iv, server_iv = derive_key_iv(shared_secret)
        self._to_server = AesCfb8Cipher(key, client_iv)
        self._to_client = AesCfb8Cipher(key, server_iv)
        self.enabled = True

    def encrypt_outgoing(self, data: bytes) -> bytes:
        if self._to_server is None:
            return data
        return self._to_server.encrypt(data)

    def decrypt_incoming(self, data: bytes) -> bytes:
        if self._to_client is None:
            return data
        return self._to_client.decrypt(data)
