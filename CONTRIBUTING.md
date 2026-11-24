# Contributing to Leafish

Thanks for your interest in contributing! Leafish is a pure Python,
asynchronous Minecraft Java Edition bot framework.

## Development setup

```bash
git clone https://github.com/leafish/leafish
cd leafish
pip install -e ".[dev]"
```

## Workflow

1. Create a branch for your change.
2. Write tests for new behavior (`tests/unit`, `tests/integration`,
   `tests/protocol`).
3. Run the checks:

   ```bash
   pytest
   ruff check
   ty check
   ```

4. Update `IMPLEMENTATION_STATUS.md` if you change what the project can do.
5. Open a pull request.

## Rules of the road

- Protocol packet IDs and layouts must come from minecraft-data
  (`protocol.json`) — never hardcode guessed values.
- No feature is "done" without tests.
- Keep secrets (tokens, passwords) out of logs and code.
- Public APIs need type annotations and docstrings.
