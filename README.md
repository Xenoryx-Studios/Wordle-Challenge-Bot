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
│  ├─ guild_config.py    # Handles guild state, schedule, and channel. this should probably move to a DB but /shrug this works for now
│  ├─ wordle_utils.py    # Word picking and posting logic
│  ├─ themes.py          # Theme configurations; only default theme exists currently
├─ cogs/
│  ├─ wordle_commands.py # Slash commands: /wordle_init, /wordle_schedule
│  ├─ scheduler.py       # Background task for automatic posting
├─ data/
│  ├─ guild_config.json  # stores state and stuff /shrug
│  ├─ wordle_words_christmas.json  # not implemented yet but maybe make some different word themes in the future?
│  ├─ wordle_words.json  # Word list for default theme
├─ requirements.txt      # Python dependencies
```

# Contributing

1. Fork the repository.
2. Make changes in your branch.
3. Submit a pull request with detailed explanation of your changes.
