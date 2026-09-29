from contextlib import contextmanager
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
    scheduler._attempted = {}
    return scheduler


def _make_channel(guild_id):
    channel = MagicMock()
    channel.guild.id = guild_id
    message = MagicMock()
    message.id = 777
    message.create_thread = AsyncMock(return_value=MagicMock(id=1))
    channel.send = AsyncMock(return_value=message)
    return channel


def _make_bot(channels):
    """channels: dict of channel id -> fake channel."""
    bot = MagicMock()
    bot.wait_until_ready = AsyncMock()
    bot.get_channel = MagicMock(side_effect=lambda cid: channels.get(cid))
    return bot


@contextmanager
def _clock(fixed_now):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.astimezone(tz) if tz else fixed_now

    with patch("cogs.scheduler.datetime", FixedDatetime), patch("core.wordle_utils.datetime", FixedDatetime):
        yield


async def _tick(scheduler, fixed_now):
    with _clock(fixed_now):
        await Scheduler.daily_task.coro(scheduler)


async def _start_server(guild_id, channel_id, tz_name, state=None):
    await guild_config.set_guild_channel(guild_id, channel_id)
    await guild_config.set_guild_schedule(guild_id, 9, 0, tz_name)
    if state is not None:
        await guild_config.set_guild_state(guild_id, state)


async def test_posts_at_midnight_local_in_each_timezone():
    # 05:00 UTC is 00:00 in Toronto (EST) but 05:00 in UTC.
    await _start_server(1, 100, "America/Toronto", {"used_words": [], "challenge_date": "2025-12-31"})
    await _start_server(2, 200, "UTC", {"used_words": [], "challenge_date": "2026-01-01"})
    toronto, utc = _make_channel(1), _make_channel(2)
    scheduler = _make_scheduler(_make_bot({100: toronto, 200: utc}))

    await _tick(scheduler, datetime(2026, 1, 1, 5, 0, tzinfo=timezone.utc))

    toronto.send.assert_awaited_once()
    utc.send.assert_not_awaited()  # UTC's Jan 1 Challenge already posted
    state = await guild_config.get_guild_state(1)
    assert state["challenge_date"] == "2026-01-01"
    assert state["post_id"] == 777


async def test_does_not_post_twice_on_the_same_day():
    await _start_server(1, 100, "UTC", {"used_words": [], "challenge_date": "2025-12-31"})
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))

    await _tick(scheduler, datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))
    await _tick(scheduler, datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
    await _tick(scheduler, datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc))

    channel.send.assert_awaited_once()


async def test_late_post_after_being_offline_at_midnight():
    # Last Challenge was two days ago; the bot comes back mid-afternoon.
    await _start_server(1, 100, "UTC", {"used_words": [], "challenge_date": "2025-12-30"})
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))

    await _tick(scheduler, datetime(2026, 1, 1, 15, 42, tzinfo=timezone.utc))
    await _tick(scheduler, datetime(2026, 1, 1, 15, 43, tzinfo=timezone.utc))

    channel.send.assert_awaited_once()
    state = await guild_config.get_guild_state(1)
    assert state["challenge_date"] == "2026-01-01"


async def test_server_without_challenge_date_waits_for_midnight():
    # Set up with the old commands: stored post time 09:00, no Challenge date.
    await _start_server(1, 100, "UTC", {"word": "CRANE", "used_words": ["CRANE"]})
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))

    await _tick(scheduler, datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc))
    await _tick(scheduler, datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc))
    channel.send.assert_not_awaited()

    await _tick(scheduler, datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc))
    channel.send.assert_awaited_once()
    state = await guild_config.get_guild_state(1)
    assert state["challenge_date"] == "2026-01-02"
    assert "CRANE" in state["used_words"]  # history kept


async def test_stopped_server_gets_no_challenge():
    await _start_server(1, 100, "UTC", {"used_words": [], "challenge_date": "2025-12-31"})
    await guild_config.clear_guild_schedule(1)
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))

    await _tick(scheduler, datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))

    channel.send.assert_not_awaited()


async def test_failed_post_is_not_retried_every_tick(word_list_file):
    # A broken word list makes post_word send a warning to the channel;
    # retrying every minute would spam that warning all day.
    await _start_server(1, 100, "UTC", {"used_words": [], "challenge_date": "2025-12-31"})
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))
    broken_theme = {"file": word_list_file([]), "message": "{word}", "thread_name": "{date}"}

    with patch.dict("cogs.scheduler.THEMES", {"default": broken_theme}):
        await _tick(scheduler, datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))
        await _tick(scheduler, datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))

    channel.send.assert_awaited_once()  # the one warning
    state = await guild_config.get_guild_state(1)
    assert state["challenge_date"] == "2025-12-31"  # no Challenge recorded


async def test_bad_timezone_does_not_stop_other_guilds():
    # A single guild with a corrupted/invalid timezone string must not
    # prevent other guilds from being processed in the same tick.
    # discord.py's tasks.loop only auto-retries a narrow set of
    # connection-related exceptions, so an unhandled exception escaping
    # the loop body would otherwise stop the scheduler for every guild,
    # silently, until the bot is restarted.
    await _start_server(1, 100, "Not/A_Real_Zone", {"used_words": [], "challenge_date": "2025-12-31"})
    await _start_server(2, 200, "UTC", {"used_words": [], "challenge_date": "2025-12-31"})
    channel = _make_channel(2)
    scheduler = _make_scheduler(_make_bot({100: _make_channel(1), 200: channel}))

    await _tick(scheduler, datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))  # should not raise

    channel.send.assert_awaited_once()
    state = await guild_config.get_guild_state(2)
    assert state["word"] is not None
