# Wordle Discord Bot

A Discord bot that posts daily Wordle challenges to your server.

- Post daily Wordle starter words automatically.
- Tracks used words to avoid repeats.
- Posts Wordle rules and creates a dedicated thread for each challenge.
- One command to start daily Challenges in a channel, in your server's timezone.

# Challenge Rules

**Wordle Challenge Rules**
1. Each day has a starter word.
2. Use it as your first guess in Wordle.
3. Try to solve in as few guesses as possible.
4. Post your Result (the Wordle share squares) in the Challenge thread.
Have fun!


# Commands

All commands except `/wordle_help` require the **Manage Server** permission and can only be used in a server (not DMs).

`/wordle_start`: Start daily Wordle Challenges in the channel where you run it.

parameters:
- timezone: IANA timezone name (e.g., `America/Toronto`). See the [list of tz database time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for accepted values: use the value from the "TZ identifier" column.

- Posts the Wordle rules and pins the message.
- Posts today's Challenge straight away, unless today's Challenge was already posted.
- From then on, posts a new Challenge every day at 00:00 in that timezone, when the new Wordle puzzle unlocks. If the bot was offline at 00:00, it posts as soon as it is back online. A server never gets more than one Challenge per day.
- Running it again moves the Challenge to the current channel and timezone from the next day, and restarts a stopped server. Used words are kept.

`/wordle_stop`: Stop daily Challenges for this server. Used words are kept, so running `/wordle_start` again picks up where you left off.

`/wordle_replace`: Replace today's Starter Word when it can't be played (not accepted by Wordle, offensive, or too obscure). Works from any channel. The new Starter Word is posted in today's Challenge thread and the original Challenge post is edited to show it was replaced; results already posted in the thread still count. Both words stay in the used-words history.

`/wordle_reset`: Clear the used-words history so previously used words can be picked again. Leaves today's already-posted word untouched.

`/wordle_status`: Show the server's posting channel and timezone (or that it is stopped), today's Starter Word, and how many words have been used so far.

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
│  ├─ wordle_commands.py        # Slash commands: /wordle_start, /wordle_stop, ...
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
