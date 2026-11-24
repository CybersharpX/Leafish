# State API

`LeafishBot` exposes live server state through dataclasses in
`leafish.modules.state` (and scoreboard models in
`leafish.modules.scoreboard`). All are updated by packet handlers —
read them synchronously.

## State properties on the bot

| Property | Type | Contents |
|---|---|---|
| `bot.health` | `float` | 0–20 HP. |
| `bot.food` | `int` | 0–20 food. |
| `bot.food_saturation` | `float` | Saturation. |
| `bot.oxygen` / `bot.oxygen_level` | `int \| None` | Air bubbles; `None` when not submerged. |
| `bot.experience` | `ExperienceInfo` | Level, points, progress, total. |
| `bot.time` | `TimeInfo` | World clock. |
| `bot.game` | `GameInfo` | Server/game info. |
| `bot.abilities` | `AbilitiesInfo` | Fly/may-fly/instabuild/etc. |
| `bot.weather` | `WeatherInfo` | Raining/thundering/levels. |
| `bot.settings` | `SettingsInfo` | Client settings (view distance, particles, hand, ...). |
| `bot.is_raining` / `bot.rain_state` / `bot.thunder_state` | `bool`/`float` | Weather shortcuts. |
| `bot.physics_enabled` | `bool` (settable) | Physics engine toggle. |
| `bot.is_sleeping` | `bool` | Sleeping state. |
| `bot.spawn_point` | `BlockPos \| None` | World spawn. |
| `bot.tablist` / `bot.players` | `dict` | Tab-list players. |
| `bot.scoreboards` / `bot.teams` / `bot.boss_bars` | `dict` | Live server state. |
| `bot.team_map` / `bot.scoreboard` | `dict`/`ScoreBoard` | Sidebar shortcuts. |
| `bot.cursor_item` | `Item \| None` | Item on the cursor. |
| `bot.quick_bar_slot` | `int` | Selected hotbar index. |
| `bot.current_window_id` | `int \| None` | Open window id. |
| `bot.target_dig_block` | `BlockPos \| None` | Block currently being dug. |

## Dataclasses

### `GameInfo`

`level_type`, `dimension`, `difficulty`, `game_mode`, `hardcore`,
`max_players`, `server_brand`, `min_y`, `height`, `view_distance`,
`simulation_distance`, `extra`.

### `TimeInfo`

`do_daylight_cycle`, `big_time` (total ticks), `time` (time-of-day
ticks), `tick_day_time`. Properties: `time_of_day`, `day`, `is_day`,
`moon_phase`, `age`.

### `ExperienceInfo`

`level`, `points`, `progress` (0–1), `total`.

### `AbilitiesInfo`

`invulnerable`, `flying`, `may_fly`, `instabuild`, `may_build`,
`flying_speed`, `walking_speed`.

### `WeatherInfo`

`raining`, `thundering`, `rain_level`, `thunder_level`.

### `SettingsInfo`

`chat_colors`, `view_distance`, `difficulty`, `skin_parts`,
`enable_text_filtering`, `enable_server_listing`, `particle_status`,
`main_hand`.

## Scoreboard models

`bot.scoreboards` maps objective name → `ScoreBoard` (`title`,
`type`, `items` → `ScoreItem`s with `name`, `score_name`, `value`,
`display_name`). `bot.teams` maps team name → `Team` (`display_name`,
`prefix`, `suffix`, `color`, `members`, ...). `bot.boss_bars` maps
UUID → `BossBar` (`title`, `health`, `color`, `flags`, ...).
