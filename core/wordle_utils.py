import json
import random
from datetime import datetime
import logging
from core.themes import THEMES
from core.guild_config import set_guild_state, get_guild_state

logger = logging.getLogger("wordle-bot")

def pick_word(theme_file, used_words=None):
    with open(theme_file, "r", encoding="utf-8") as f:
        words = [w.upper() for w in json.load(f)]
    if used_words is None:
        used_words = []

    available_words = [w for w in words if w not in used_words]
    if not available_words:
        used_words = []
        available_words = words.copy()

    word = random.choice(available_words)
    used_words.append(word)
    return word, used_words

async def post_word(bot, channel_id, theme, state):
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.error(f"Channel {channel_id} not found")
        return

    # Load state from guild_config if state is None
    if state is None:
        # You can retrieve guild_id via channel.guild.id or pass it as arg
        pass

    used = state.get("used_words", []) if state else []
    word, used = pick_word(theme["file"], used_words=used)
    if state:
        state["word"] = word
        state["used_words"] = used
        set_guild_state(channel.guild.id, state)

    logger.info(f"Posting word '{word}' in channel {channel_id}")

    date_str = datetime.now().strftime("%b %d")
    msg = await channel.send(theme["message"].format(word=word))

    try:
        thread = await msg.create_thread(
            name=theme["thread_name"].format(date=date_str),
            auto_archive_duration=1440
        )
        if state:
            state["thread_id"] = thread.id
            set_guild_state(channel.guild.id, state)
        logger.info(f"Thread created {thread.id} for word '{word}'")
    except Exception as e:
        logger.warning(f"Cannot create thread: {e}")