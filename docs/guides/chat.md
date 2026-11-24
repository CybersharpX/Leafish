# Chat & commands

## Sending

| Method | Sends |
|---|---|
| `await bot.chat(msg)` | A normal chat message. |
| `await bot.command(cmd)` / `await bot.chat_command(cmd)` | A slash command (`cmd` may include or omit the leading `/`). |
| `await bot.whisper(user, msg)` | `/msg <user> <msg>` |
| `await bot.me(msg)` | `/me <msg>` |

Messages are length-checked client-side; very long lines are split or
rejected by the server — keep under ~256 chars.

## Receiving

```python
@bot.on("chat")
async def on_chat(username, message):
    print(f"<{username}> {message}")

@bot.on("whisper")
async def on_whisper(username, message):
    print(f"whisper from {username}: {message}")
```

System messages (join/leave, death, advancements) arrive as plain
chat-text events or via the dedicated events below.

## Matching server messages

```python
bot.add_chat_pattern("death", r"(\w+) (?:was|fell|drowned) .*", "chat")
bot.on("death", lambda match: print("died:", match))

bot.add_chat_pattern_set("rcon", {
    "broadcast": r"\[Server\] (.*)",
}, "system")

bot.remove_chat_pattern("death")
```

`chat_type` is `"chat"` or `"system"` — register the right one for the
channel you want to match.

## Waiting for a message

```python
match = await bot.await_message(r"You (?:got|received) (.+)", timeout=30)
```

Returns the regex match (or `None` on timeout).

## Tab completion

```python
suggestions = await bot.tab_complete("/give ", assume_command=True)
# suggestions: list[str]
```

The result is emitted as a `chat_suggestions` event and returned by
the call.
