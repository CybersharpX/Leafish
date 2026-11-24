<div align="center">

# 🍃 Leafish

**A pure Python, asyncio-native Minecraft Java Edition bot framework.**

Join servers, chat, move, mine, build, craft, fight, and automate, with no Node.js and no external bot process.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](IMPLEMENTATION_STATUS.md)

[Quick start](#-quick-start) · [Features](#-features) · [Status](#-project-status) · [Roadmap](ROADMAP.md) · [Contributing](#-contributing)

</div>

---

## Why Leafish?

Leafish is inspired by [Mineflayer](https://github.com/PrismarineJS/mineflayer), built for Python developers who want a first-class bot framework in their own language.

- **Pure Python.** The Minecraft protocol is implemented natively. Nothing to install beyond Python itself.
- **Async by design.** Built on `asyncio`, so you can run many bots, or a bot alongside a web server, in a single process.
- **Event-driven.** Subscribe to what happens in the world with simple decorators.
- **Honest about progress.** Features are not advertised until they are implemented and tested. See the [implementation status](IMPLEMENTATION_STATUS.md).

## ✨ Features

| Area | Goal |
| --- | --- |
| **Protocol** | Native Java Edition protocol, multi-version support driven by vendored [minecraft-data](https://github.com/PrismarineJS/minecraft-data) |
| **Authentication** | Offline and Microsoft accounts |
| **API** | Async, event-driven, with plugin support |
| **World model** | Chunk, entity, and inventory tracking |
| **Automation** | Pathfinding, digging, placing, crafting, combat, containers |

> [!NOTE]
> Leafish is under active development. The table above describes the project's goals, and the [implementation status](IMPLEMENTATION_STATUS.md) tracks what actually works today.

## 📦 Installation

Requires **Python 3.11+**.

```bash
pip install leafish
```

<details>
<summary><b>Install for development</b></summary>

```bash
git clone https://github.com/leafish/leafish
cd leafish
pip install -e ".[dev]"
```

</details>

## 🚀 Quick start

```python
import asyncio
from leafish import Leafish


async def main():
    bot = await Leafish.create_bot(
        host="localhost",
        port=25565,
        username="Leafish",
        auth="offline",
    )

    @bot.on("spawn")
    async def on_spawn():
        print("Leafish joined the world!")

    @bot.on("chat")
    async def on_chat(username, message):
        print(f"<{username}> {message}")

    await bot.wait_until_disconnected()


asyncio.run(main())
```

Start a local Minecraft Java server in offline mode, run the script, and watch the bot join.

## 📊 Project status

Leafish is built incrementally: protocol layer first, then the bot API, world model, and automation modules.

| Document | What it covers |
| --- | --- |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | The current, per-subsystem state of what is implemented and tested |
| [ROADMAP.md](ROADMAP.md) | Where the project is headed next |

## 🤝 Contributing

Contributions are welcome. To get set up:

```bash
git clone https://github.com/leafish/leafish
cd leafish
pip install -e ".[dev]"
```

Before opening a pull request, please check [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) so your work lines up with what's in progress, and keep docs honest: only document features that are implemented and tested.

## 📄 License

Released under the [MIT License](LICENSE).
