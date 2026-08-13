import logging
from datetime import datetime, timezone

import discord
import pytz
from discord.ext import commands, tasks

from core.guild_config import load_guild_config, set_guild_state
from core.themes import THEMES
from core.wordle_utils import post_word

logger = logging.getLogger("wordle-bot")

class Scheduler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_task.start()

    def cog_unload(self):
        self.daily_task.cancel()

    @tasks.loop(seconds=60)
    async def daily_task(self):
        await self.bot.wait_until_ready()
        guild_configs = await load_guild_config()
        theme = THEMES.get("default")

        now_utc = datetime.now(timezone.utc)
        for guild_id_str, data in guild_configs.items():
            # Guard the whole per-guild body: any unhandled exception here
            # (bad timezone string, malformed config, etc.) would otherwise
            # propagate out of this loop and permanently stop the task for
            # every guild, since discord.py's tasks.loop only auto-retries
            # a narrow set of connection-related exceptions.
            try:
                channel_id = data.get("channel_id")
                hour = data.get("hour", 0)
                minute = data.get("minute", 0)
                tz_name = data.get("timezone", "UTC")
                state = data.get("state", {"word": None, "used_words": [], "thread_id": None})

                if not channel_id:
                    continue

                tz = pytz.timezone(tz_name)
                now_local = now_utc.astimezone(tz)

                if now_local.hour == hour and now_local.minute == minute:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        continue
                    await post_word(self.bot, channel_id, theme, state, timezone_name=tz_name)
                    # Persist only this guild's state so we don't clobber
                    # other guilds' updates made since this loop's config
                    # snapshot was loaded.
                    await set_guild_state(guild_id_str, state)
            except discord.Forbidden:
                logger.warning(f"Missing permissions for {channel_id} in guild {guild_id_str}")
            except Exception:
                logger.exception(f"Error processing scheduled post for guild {guild_id_str}")

    @daily_task.before_loop
    async def before_daily_task(self):
        await self.bot.wait_until_ready()

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(Scheduler(bot))
