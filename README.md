# Wordle Discord Bot

A Discord bot that posts daily Wordle challenges to your server.

- Post daily Wordle starter words automatically.
- Tracks used words to avoid repeats.
- Posts Wordle rules and creates a dedicated thread for each challenge.
- Commands to manually initialize Wordle or set schedules.


# Commands

`/wordle_init` : Initialize today's Wordle manually.

- Posts the Wordle rules.
- Picks today's Wordle word.
- Creates a thread for discussion.

`/wordle_schedule`: Set a daily posting time for Wordle Challenge.

paramaters:
- hour: Hour in 24-hour format (0-23)
- minute: Minute (0-59)
- timezone: IANA timezone name (e.g., America/Toronto)

# File Structure
```
wordle-discord-bot/
├─ bot.py                # Main bot entry
├─ core/
│  ├─ guild_config.py    # Handles per-guild state, schedule, and channel
│  ├─ wordle_utils.py    # Word picking and posting logic
│  ├─ themes.py          # Theme configurations
├─ cogs/
│  ├─ wordle_commands.py # Slash commands: init, schedule
│  ├─ scheduler.py       # Background task for automatic posting
├─ data/
│  ├─ wordle_words.json  # Word list for default theme
├─ requirements.txt      # Python dependencies
```

# Contributing

1. Fork the repository.
2. Make changes in your branch.
3. Submit a pull request with detailed explanation of your changes.