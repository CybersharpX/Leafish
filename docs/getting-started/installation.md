# Installation

Leafish requires **Python 3.11 or newer**.

## From PyPI

```bash
pip install leafish
```

## From source

```bash
git clone https://github.com/CybersharpX/Leafish.git
cd Leafish
pip install -e ".[dev]"
```

The `dev` extra installs the test, lint, type-checking and docs
toolchain (pytest, ruff, ty, mkdocs).

## Runtime dependencies

| Package | Purpose |
|---|---|
| `httpx` | Microsoft authentication HTTP calls |
| `cryptography` | RSA key exchange + AES/CFB8 transport encryption |
| `protolib` | ProtoDef-compatible packet serialization |

There is no Node.js dependency and no JavaScript runtime anywhere in
the stack.

## Verifying the install

```python
import leafish
print(leafish.__version__ if hasattr(leafish, "__version__") else "ok")
from leafish.data.registry import get_gamedata
gd = get_gamedata("1.21.11")
print(gd.item_by_name("diamond"))
```

## Documentation site

To build the docs locally:

```bash
pip install mkdocs mkdocs-shadcn
mkdocs serve
```
