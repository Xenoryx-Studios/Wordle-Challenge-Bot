import logging
from datetime import datetime, timezone

import discord
import pytz
from discord.ext import commands, tasks

from core.guild_config import get_guild_entry, load_guild_config, set_guild_state
from core.settings import REMINDER_HOUR, reminders_enabled
from core.themes import get_theme
from core.wordle_utils import find_thread, is_result, post_word

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
            # Guard each per-guild step: any unhandled exception here (bad
            # timezone string, malformed config, etc.) would otherwise
            # propagate out of this loop and permanently stop the task for
            # every guild, since discord.py's tasks.loop only auto-retries
            # a narrow set of connection-related exceptions.
            try:
                await self._post_challenge_if_due(guild_id_str, data, now_utc)
            except discord.Forbidden:
                logger.warning(f"Missing permissions for {data.get('channel_id')} in guild {guild_id_str}")
            except Exception:
                logger.exception(f"Error processing scheduled post for guild {guild_id_str}")

            if reminders_enabled():
                try:
                    await self._send_reminder_if_due(guild_id_str, now_utc)
                except Exception:
                    logger.exception(f"Error processing Reminder for guild {guild_id_str}")

    async def _post_challenge_if_due(self, guild_id_str, data, now_utc):
        # A server with no posting channel is Stopped. Any stored hour/minute
        # from the old scheduling command is ignored: Challenges always post
        # at 00:00 local.
        channel_id = data.get("channel_id")
        tz_name = data.get("timezone", "UTC")
        state = data.get("state", {"word": None, "used_words": [], "thread_id": None})

        if not channel_id:
            return

        tz = pytz.timezone(tz_name)
        now_local = now_utc.astimezone(tz)
        today = now_local.date().isoformat()

        if not challenge_due(state, now_local):
            return
        if self._attempted.get(guild_id_str) == today:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        self._attempted[guild_id_str] = today
        theme = get_theme(data.get("theme"))
        if await post_word(self.bot, channel_id, theme, state, timezone_name=tz_name):
            # Persist only this guild's state so we don't clobber other
            # guilds' updates made since this loop's config snapshot was
            # loaded.
            await set_guild_state(guild_id_str, state)

    async def _send_reminder_if_due(self, guild_id_str, now_utc):
        # Read fresh: a Challenge may have just been posted above.
        entry = await get_guild_entry(guild_id_str)
        members = entry.get("reminder_members", [])
        if not entry.get("channel_id") or not members:
            return  # Stopped, or nobody opted in

        tz = pytz.timezone(entry.get("timezone", "UTC"))
        now_local = now_utc.astimezone(tz)
        today = now_local.date().isoformat()
        state = entry.get("state", {})
        if state.get("challenge_date") != today or state.get("reminder_date") == today:
            return
        if now_local.hour < REMINDER_HOUR:
            return
        # A Challenge that only posted at or after the Reminder Time (e.g. a
        # late post after downtime) gets no Reminder that day.
        posted_local = discord.utils.snowflake_time(state["post_id"]).astimezone(tz)
        if posted_local.hour >= REMINDER_HOUR:
            return

        # Mark the day as done before sending, so a failing send is not
        # retried every tick.
        state["reminder_date"] = today
        await set_guild_state(guild_id_str, state)

        thread = await find_thread(self.bot, state.get("thread_id"))
        if thread is None:
            logger.warning(f"No Challenge thread for today's Reminder in guild {guild_id_str}")
            return

        played = {message.author.id async for message in thread.history(limit=None) if is_result(message.content)}
        guild = self.bot.get_guild(int(guild_id_str))
        if guild is None:
            return  # the bot is no longer in this server
        pending = []
        for member_id in members:
            if member_id in played:
                continue
            try:
                await guild.fetch_member(member_id)
            except discord.NotFound:
                continue  # left the server
            pending.append(member_id)

        if not pending:
            return
        mentions = " ".join(f"<@{member_id}>" for member_id in pending)
        await thread.send(
            f"⏰ Reminder: {mentions} you haven't posted your Result for today's Challenge yet. "
            "The Wordle resets at midnight!",
            allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=m) for m in pending]),
        )

    @daily_task.before_loop
    async def before_daily_task(self):
        await self.bot.wait_until_ready()

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(Scheduler(bot))
