from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from cogs.scheduler import Scheduler
from core import guild_config


def _make_scheduler(bot):
    # Bypass __init__ (which calls self.daily_task.start() and would spin
    # up the real 60s background loop) and drive one iteration of the loop
    # body directly via the underlying coroutine instead.
    scheduler = Scheduler.__new__(Scheduler)
    scheduler.bot = bot
    return scheduler


async def test_daily_task_bad_timezone_does_not_stop_other_guilds():
    # A single guild with a corrupted/invalid timezone string must not
    # prevent other guilds from being processed in the same tick.
    # discord.py's tasks.loop only auto-retries a narrow set of
    # connection-related exceptions, so an unhandled exception escaping
    # the loop body would otherwise stop the scheduler for every guild,
    # silently, until the bot is restarted.
    await guild_config.set_guild_channel(1, 100)
    await guild_config.set_guild_schedule(1, 9, 0, "Not/A_Real_Zone")

    await guild_config.set_guild_channel(2, 200)
    await guild_config.set_guild_schedule(2, 9, 0, "UTC")

    channel = MagicMock()
    channel.guild.id = 2
    message = MagicMock()
    message.create_thread = AsyncMock(return_value=MagicMock(id=1))
    channel.send = AsyncMock(return_value=message)

    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    bot.get_channel = MagicMock(return_value=channel)

    scheduler = _make_scheduler(bot)

    fixed_now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.astimezone(tz) if tz else fixed_now

    with patch("cogs.scheduler.datetime", FixedDatetime):
        await Scheduler.daily_task.coro(scheduler)  # should not raise

    # Guild 2 (valid timezone) still got processed despite guild 1's bad data.
    channel.send.assert_awaited()
    state = await guild_config.get_guild_state(2)
    assert state["word"] is not None
