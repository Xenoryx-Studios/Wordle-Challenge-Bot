import asyncio
import json
import logging
import random
from datetime import datetime, timezone

import discord
import pytz

from core.guild_config import set_guild_state

logger = logging.getLogger("wordle-bot")

_word_list_cache = {}


def _load_words_sync(theme_file):
    with open(theme_file, "r", encoding="utf-8") as f:
        return [w.upper() for w in json.load(f)]


async def _get_words(theme_file):
    if theme_file not in _word_list_cache:
        words = await asyncio.to_thread(_load_words_sync, theme_file)
        if not words:
            raise ValueError(f"Word list '{theme_file}' is empty")
        _word_list_cache[theme_file] = words
    return _word_list_cache[theme_file]


async def pick_word(theme_file, used_words=None):
    words = await _get_words(theme_file)
    if used_words is None:
        used_words = []

    used_set = set(used_words)
    available_words = [w for w in words if w not in used_set]
    if not available_words:
        used_words = []
        available_words = words.copy()

    word = random.choice(available_words)
    used_words.append(word)
    return word, used_words

async def post_word(bot, channel_id, theme, state, timezone_name="UTC"):
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.error(f"Channel {channel_id} not found")
        return

    used = state.get("used_words", []) if state is not None else []
    try:
        word, used = await pick_word(theme["file"], used_words=used)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to pick a word from '{theme['file']}': {e}")
        await channel.send(
            "⚠️ Couldn't load today's Wordle word — the word list may be missing or empty. "
            "Please contact a server admin."
        )
        return
    if state is not None:
        state["word"] = word
        state["used_words"] = used
        await set_guild_state(channel.guild.id, state)

    logger.info(f"Posting word '{word}' in channel {channel_id}")

    try:
        tz = pytz.timezone(timezone_name)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(f"Unknown timezone '{timezone_name}', falling back to UTC for thread date")
        tz = timezone.utc
    date_str = datetime.now(tz).strftime("%b %d")
    msg = await channel.send(theme["message"].format(word=word))

    try:
        thread = await msg.create_thread(
            name=theme["thread_name"].format(date=date_str),
            auto_archive_duration=1440
        )
        if state is not None:
            state["thread_id"] = thread.id
            await set_guild_state(channel.guild.id, state)
        logger.info(f"Thread created {thread.id} for word '{word}'")
    except discord.HTTPException as e:
        logger.warning(f"Cannot create thread: {e}")
