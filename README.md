# Wordle Discord Bot

A Discord bot that posts daily Wordle challenges to your server.

- Post daily Wordle starter words automatically.
- Tracks used words to avoid repeats.
- Posts Wordle rules and creates a dedicated thread for each challenge.
- Commands to manually initialize Wordle or set schedules.

# Challenge Rules

**Wordle Challenge Rules**
1. Each day has a starter word.
2. Use it as your first guess in Wordle.
3. Try to solve in as few guesses as possible.
4. Post your results in the channel using the Wordle share squares.
Have fun!


# Commands

All commands except `/wordle_help` require the **Manage Server** permission and can only be used in a server (not DMs).

`/wordle_init` : Initialize today's Wordle manually.

- Posts the Wordle rules and pins the message.
- Picks today's Wordle word.
- Creates a thread for discussion.
- Preserves any existing used-words history (does not reset it).

`/wordle_schedule`: Set a daily posting time for Wordle Challenge.

parameters:
- hour: Hour in 24-hour format (0-23)
- minute: Minute (0-59)
- timezone: IANA timezone name (e.g., `America/Toronto`). See the [list of tz database time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for accepted values — use the value from the "TZ identifier" column.

`/wordle_stop`: Disable automatic daily posting for this server. Word history is preserved — running `/wordle_schedule` again re-enables it.

`/wordle_skip`: Post a new Wordle word right now, in the current channel, without reposting the rules or creating a new pinned message.

`/wordle_reset`: Clear the used-words history so previously used words can be picked again. Leaves today's already-posted word untouched.

`/wordle_status`: Show the server's current posting channel, schedule, today's word, and how many words have been used so far.

`/wordle_help`: Post the Wordle Challenge rules. Available to everyone, no permission required.

# Running the Bot

## Locally

```
pip install -r requirements.txt
export DISCORD_TOKEN=your-bot-token   # or set it in your environment however you prefer
python bot.py
```

## Docker

```
make build
make run TOKEN=your-bot-token
make logs
make stop
```

`make run` mounts `./data` into the container so word lists and per-server state persist across restarts. The real `data/guild_config.json` is created automatically on first run and is gitignored — `data/guild_config.example.json` is the committed template.

# Development

Install dev dependencies and run the test suite:

```
pip install -r requirements-dev.txt
pytest -v
ruff check .
```

CI (`.github/workflows/ci.yml`) runs lint and tests on every push/PR, and only builds & publishes a Docker image to GHCR after both pass on `main`.

# File Structure
```
wordle-discord-bot/
├─ bot.py                       # Main bot entry
├─ core/
│  ├─ guild_config.py           # Async, lock-guarded, atomic per-guild config storage
│  ├─ wordle_utils.py           # Word picking and posting logic
│  ├─ themes.py                 # Theme configurations; only "default" is wired to a command currently
├─ cogs/
│  ├─ wordle_commands.py        # Slash commands: /wordle_init, /wordle_schedule
│  ├─ scheduler.py              # Background task for automatic posting
├─ data/
│  ├─ guild_config.example.json # Template for the runtime state file (gitignored)
│  ├─ wordle_words_christmas.json  # Not wired to any command yet
│  ├─ wordle_words.json         # Word list for the default theme
├─ tests/                       # pytest suite for core/
├─ .github/workflows/ci.yml     # Lint -> test -> build & push (gated)
├─ Dockerfile
├─ .dockerignore
├─ makefile
├─ requirements.txt             # Runtime dependencies
├─ requirements-dev.txt         # + pytest/pytest-asyncio for local testing and CI
```

# Contributing

1. Fork the repository.
2. Make changes in your branch.
3. Submit a pull request with detailed explanation of your changes.
