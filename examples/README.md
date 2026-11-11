# Examples

Runnable example bots. Each connects to a Java 1.21.11 server (offline
auth works on `online-mode=false` servers) and demonstrates one feature.

| Script | Demonstrates |
|---|---|
| `echo_bot.py` | connect, spawn event, chat send/receive |
| `goto_example.py` | A* pathfinding + `bot.goto` |
| `collector.py` | world queries (`block_at`, `can_dig_block`) + `bot.dig` |

Run from the repo root with the project installed (`pip install -e .`):

```bash
python examples/echo_bot.py localhost 25565 MyBot
```
