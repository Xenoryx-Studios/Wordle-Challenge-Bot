import logging
from datetime import datetime, timezone

import discord
import pytz
from discord.ext import commands, tasks

from core.guild_config import load_guild_config, set_guild_state
from core.themes import get_theme
from core.wordle_utils import post_word

logger = logging.getLogger("wordle-bot")

def challenge_due(state, now_local):
    """Whether a server with this state needs today's Challenge posted now.

    A server with a recorded Challenge date gets a Challenge whenever that
    date is before today, so a bot that was offline at 00:00 posts as soon
    as it is back. A server with no Challenge date yet (set up before dates
    were recorded) waits for 00:00, so upgrading does not post a second
    Challenge on a day that already had one.
    """
    today = now_local.date().isoformat()
    challenge_date = state.get("challenge_date")
    if challenge_date is None:
        return now_local.hour == 0 and now_local.minute == 0
    return challenge_date < today


class Scheduler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild id -> local date of the last attempted post, so a Challenge
        # that fails to post (e.g. a broken word list, which also sends a
        # warning to the channel) is tried once per day instead of every tick.
        self._attempted = {}
        self.daily_task.start()

    def cog_unload(self):
        self.daily_task.cancel()

    @tasks.loop(seconds=60)
    async def daily_task(self):
        await self.bot.wait_until_ready()
        guild_configs = await load_guild_config()

        now_utc = datetime.now(timezone.utc)
        for guild_id_str, data in guild_configs.items():
            # Guard the whole per-guild body: any unhandled exception here
            # (bad timezone string, malformed config, etc.) would otherwise
            # propagate out of this loop and permanently stop the task for
            # every guild, since discord.py's tasks.loop only auto-retries
            # a narrow set of connection-related exceptions.
            try:
                # A server with no posting channel is Stopped. Any stored
                # hour/minute from the old scheduling command is ignored:
                # Challenges always post at 00:00 local.
                channel_id = data.get("channel_id")
                tz_name = data.get("timezone", "UTC")
                state = data.get("state", {"word": None, "used_words": [], "thread_id": None})

                if not channel_id:
                    continue

                tz = pytz.timezone(tz_name)
                now_local = now_utc.astimezone(tz)
                today = now_local.date().isoformat()

                if not challenge_due(state, now_local):
                    continue
                if self._attempted.get(guild_id_str) == today:
                    continue

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                self._attempted[guild_id_str] = today
                theme = get_theme(data.get("theme"))
                if await post_word(self.bot, channel_id, theme, state, timezone_name=tz_name):
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
