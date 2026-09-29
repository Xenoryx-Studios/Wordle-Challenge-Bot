import os

import discord

REMINDER_HOUR = 21  # three hours before the Wordle puzzle resets at 00:00


def reminders_enabled(env=None):
    """Whether the host has turned on Reminders with ENABLE_REMINDERS."""
    env = os.environ if env is None else env
    return env.get("ENABLE_REMINDERS", "").strip().lower() in {"1", "true", "yes", "on"}


def build_intents(env=None):
    """Gateway intents for the bot.

    Message Content is privileged: requesting it without enabling it in the
    Discord developer portal stops the bot connecting, so it is only
    requested when Reminders are on (see docs/adr/0001).
    """
    intents = discord.Intents.default()
    if reminders_enabled(env):
        intents.message_content = True
    return intents
