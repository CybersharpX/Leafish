"""Canonical event names emitted by Leafish bots.

These are constants for documentation and autocomplete; events are plain
strings and plugins may emit or listen to custom events freely.
"""

# Connection lifecycle
CONNECT = "connect"
LOGIN = "login"
SPAWN = "spawn"
END = "end"
ERROR = "error"
KICKED = "kicked"
DISCONNECT = "disconnect"
RECONNECT = "reconnect"

# Player
CHAT = "chat"
WHISPER = "whisper"
PLAYER_JOIN = "player_join"
PLAYER_LEAVE = "player_leave"
PLAYER_UPDATED = "player_updated"

# World
CHUNK_COLUMN_LOAD = "chunk_column_load"
CHUNK_COLUMN_UNLOAD = "chunk_column_unload"
BLOCK_UPDATE = "block_update"
BLOCK_ENTITY_UPDATE = "block_entity_update"
WEATHER_UPDATE = "weather_update"
TIME_UPDATE = "time_update"
GAME_STATE_CHANGE = "game_state_change"

# Entities
ENTITY_SPAWN = "entity_spawn"
ENTITY_UPDATE = "entity_update"
ENTITY_MOVE = "entity_move"
ENTITY_DESTROY = "entity_destroy"
ENTITY_HURT = "entity_hurt"
ENTITY_EQUIPMENT_UPDATE = "entity_equipment_update"
ENTITY_METADATA_UPDATE = "entity_metadata_update"

# Inventory
INVENTORY_UPDATE = "inventory_update"
WINDOW_OPEN = "window_open"
WINDOW_CLOSE = "window_close"
HELD_ITEM_CHANGED = "held_item_changed"
HEALTH = "health"
FOOD = "food"
EXPERIENCE = "experience"

# Movement
MOVE = "move"
FORCED_MOVE = "forced_move"
PHYSICS_TICK = "physics_tick"
PATH_UPDATE = "path_update"

# Actions
DIGGING_STARTED = "digging_started"
DIGGING_COMPLETED = "digging_completed"
DIGGING_ABORTED = "digging_aborted"
BLOCK_PLACED = "block_placed"
ITEM_CRAFTED = "item_crafted"
ITEM_COLLECTED = "item_collected"
