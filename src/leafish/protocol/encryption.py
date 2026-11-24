"""AES/CFB8 stream encryption used by Minecraft's encryption handshake.

Minecraft uses AES/CFB8 with:
  - key   = shared_secret   (16 bytes, same for both directions)
  - IV    = shared_secret   (16 bytes, same for both directions)

Both the client→server and server→client streams use the same key and IV but
maintain independent cipher state (separate encryptor / decryptor objects).
"""

from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

try:
    from cryptography.hazmat.decrepit.ciphers.modes import CFB8
except ImportError:
    from cryptography.hazmat.primitives.ciphers.modes import CFB8  # type: ignore[no-redef]


class AesCfb8Cipher:
    """AES/CFB8 cipher matching Minecraft's shared-secret encryption.

    ``key`` and ``iv`` are both the 16-byte shared secret for a standard
    Minecraft connection.
    """

    def __init__(self, key: bytes, iv: bytes) -> None:
        if len(key) != 16:
            raise ValueError("AES key must be 16 bytes")
        # Minecraft uses AES in CFB8 mode (8-bit segments).
        self._encryptor = Cipher(algorithms.AES(key), CFB8(iv)).encryptor()
        self._decryptor = Cipher(algorithms.AES(key), CFB8(iv)).decryptor()

    def encrypt(self, data: bytes) -> bytes:
        return self._encryptor.update(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._decryptor.update(data)


class EncryptionHandler:
    """Bidirectional encryption state for a connection.

    Call :meth:`enable` with the 16-byte shared secret received during the
    login handshake.  Minecraft uses the same secret as both AES key and IV
    for both stream directions.
    """

    def __init__(self) -> None:
        self.enabled = False
        self._to_server: AesCfb8Cipher | None = None
        self._to_client: AesCfb8Cipher | None = None

    def enable(self, shared_secret: bytes) -> None:
        """Enable AES/CFB8 encryption with *shared_secret* as key and IV."""
        if len(shared_secret) != 16:
            raise ValueError(
                f"Shared secret must be 16 bytes, got {len(shared_secret)}"
            )
        # Both directions use the same key and IV but independent cipher state.
        self._to_server = AesCfb8Cipher(shared_secret, shared_secret)
        self._to_client = AesCfb8Cipher(shared_secret, shared_secret)
        self.enabled = True

    def encrypt_outgoing(self, data: bytes) -> bytes:
        if self._to_server is None:
            return data
        return self._to_server.encrypt(data)

    def decrypt_incoming(self, data: bytes) -> bytes:
        if self._to_client is None:
            return data
        return self._to_client.decrypt(data)

