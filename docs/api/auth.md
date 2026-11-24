# Authentication API

## AuthSession

`leafish.auth.session.AuthSession` — the result of any auth provider:

| Field | Type | Meaning |
|---|---|---|
| `username` | `str` | Profile name for login. |
| `uuid` | `str` | Player UUID. |
| `access_token` | `str` | Token sent in login start. |
| `online` | `bool` | `True` for Microsoft-authenticated sessions. |

## Providers

Both implement `AuthProvider.authenticate(username=None) ->
AuthSession`.

### `OfflineAuth`

`leafish.auth.offline.OfflineAuth` — generates the offline UUID
(`offline_uuid(username)`) and returns a session immediately. No
network.

### `MicrosoftAuth`

`leafish.auth.microsoft.MicrosoftAuth` — device-code OAuth → Xbox
Live → XSTS → Minecraft Services.

```python
async with MicrosoftAuth(cache_path=Path("tokens.json")) as auth:
    session = await auth.authenticate()
    session = await auth.refresh()       # force refresh
```

Key methods: `authenticate(username=None)`, `refresh()`, `close()`.
`_save_cache`/`_load_cache` persist MSA + XSTS tokens under
`cache_path` (default `~/.leafish/`).

### Errors

Auth failures raise `AuthenticationError`; network/protocol problems
raise `ConnectionError`/`ProtocolError` — see
[Exceptions](exceptions.md).
