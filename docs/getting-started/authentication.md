# Authentication

Leafish supports two auth modes, selected with `auth=` on
`Leafish.create_bot`.

## Offline mode

```python
bot = await Leafish.create_bot(
    host="localhost", username="Steve", auth="offline",
)
```

The client generates an offline-mode UUID from the username. Works on
servers running `online-mode=false` (typical for LAN worlds and most
private servers).

## Microsoft mode

```python
bot = await Leafish.create_bot(
    host="example.com", auth="microsoft",
)
```

The flow is fully native Python (`src/leafish/auth/microsoft.py`):

1. **Device-code OAuth** against Microsoft accounts — on first run a
   code is printed; open the URL, sign in, and the token is cached.
2. **Xbox Live** authentication with the MSA token.
3. **XSTS** token for Xbox Live services.
4. **Minecraft Services** — profile + access token used for login.

### Token caching

Tokens are cached so subsequent runs skip the device-code step:

- Default cache path comes from `BotConfig.token_cache_path`
  (typically `~/.leafish/`).
- Override per-bot: `Leafish.create_bot(..., token_cache_path=Path(...))`.

### Customization

`MicrosoftAuth` can also be driven manually:

```python
from leafish.auth.microsoft import MicrosoftAuth

async with MicrosoftAuth(cache_path=Path("tokens.json")) as auth:
    session = await auth.authenticate()   # AuthSession
    session = await auth.refresh()         # force token refresh
```

`AuthSession` carries `username`, `uuid`, `access_token` and
`online` (True for Microsoft auth).

## AuthSession

| Field | Description |
|---|---|
| `username` | Profile name sent to the server. |
| `uuid` | Player UUID (offline UUIDs are name-derived). |
| `access_token` | Token sent in the login start packet. |
| `online` | `True` when authenticated through Microsoft. |
