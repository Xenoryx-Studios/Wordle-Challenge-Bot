from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

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
    await guild_config.set_guild_timezone(guild_id, tz_name)
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
    await guild_config.save_guild_config({"1": {"channel_id": 100, "hour": 9, "minute": 0, "timezone": "UTC"}})
    await guild_config.set_guild_state(1, {"word": "CRANE", "used_words": ["CRANE"]})
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))

    await _tick(scheduler, datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc))
    await _tick(scheduler, datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc))
    channel.send.assert_not_awaited()

    await _tick(scheduler, datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc))
    channel.send.assert_awaited_once()
    state = await guild_config.get_guild_state(1)
    assert state["challenge_date"] == "2026-01-02"
    assert "CRANE" in state["used_words"]["default"]  # legacy history kept as the default Theme's


async def test_stopped_server_gets_no_challenge():
    await _start_server(1, 100, "UTC", {"used_words": [], "challenge_date": "2025-12-31"})
    await guild_config.stop_guild(1)
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
    broken_theme = {"name": "default", "file": word_list_file([]), "message": "{word}", "thread_name": "{date}"}

    with patch.dict("core.themes.THEMES", {"default": broken_theme}):
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


async def test_next_challenge_uses_the_selected_theme():
    await _start_server(1, 100, "UTC", {"used_words": {"default": ["CRANE"]}, "challenge_date": "2025-12-31"})
    await guild_config.set_guild_theme(1, "halloween")
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))

    await _tick(scheduler, datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))

    state = await guild_config.get_guild_state(1)
    assert state["theme"] == "halloween"
    assert "Halloween" in channel.send.await_args.args[0]
    assert "Halloween" in channel.send.return_value.create_thread.await_args.kwargs["name"]
    assert state["used_words"]["halloween"] == [state["word"]]
    assert state["used_words"]["default"] == ["CRANE"]  # other Themes untouched


async def test_theme_running_out_clears_only_its_own_used_words(word_list_file):
    tiny = {"name": "halloween", "display_name": "Halloween", "file": word_list_file(["ghost"]),
            "message": "{word}", "thread_name": "{date}"}
    await _start_server(1, 100, "UTC", {
        "used_words": {"default": ["CRANE"], "halloween": ["GHOST"]}, "challenge_date": "2025-12-31",
    })
    await guild_config.set_guild_theme(1, "halloween")
    channel = _make_channel(1)
    scheduler = _make_scheduler(_make_bot({100: channel}))

    with patch.dict("core.themes.THEMES", {"halloween": tiny}):
        await _tick(scheduler, datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))

    state = await guild_config.get_guild_state(1)
    assert state["used_words"] == {"default": ["CRANE"], "halloween": ["GHOST"]}  # restarted with GHOST


# --- Reminders ---------------------------------------------------------------

THREAD_ID = 500
MIDNIGHT = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
LEFT_MEMBER = 99


def _message(author_id, content):
    message = MagicMock()
    message.author.id = author_id
    message.content = content
    return message


def _make_thread(messages):
    thread = MagicMock()
    thread.send = AsyncMock()

    def history(limit=None):
        async def gen():
            for message in messages:
                yield message
        return gen()

    thread.history = MagicMock(side_effect=history)
    return thread


def _make_reminder_bot(thread):
    bot = _make_bot({100: _make_channel(1), THREAD_ID: thread})
    guild = MagicMock()

    async def fetch_member(member_id):
        if member_id == LEFT_MEMBER:
            raise discord.NotFound(MagicMock(status=404), "unknown member")
        return MagicMock(id=member_id)

    guild.fetch_member = AsyncMock(side_effect=fetch_member)
    bot.get_guild = MagicMock(return_value=guild)
    bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "gone"))
    return bot


async def _server_with_challenge(members, posted_at=MIDNIGHT, challenge_date="2026-01-01"):
    await _start_server(1, 100, "UTC", {
        "word": "CRANE",
        "used_words": {"default": ["CRANE"]},
        "challenge_date": challenge_date,
        "post_id": discord.utils.time_snowflake(posted_at),
        "thread_id": THREAD_ID,
    })
    for member in members:
        await guild_config.set_reminder_opt_in(1, member, True)


@pytest.fixture
def reminders_on(monkeypatch):
    monkeypatch.setenv("ENABLE_REMINDERS", "1")


async def test_reminder_mentions_only_opted_in_members_without_a_result(reminders_on):
    await _server_with_challenge([1, 2, 3, 4, 5, 6, LEFT_MEMBER])
    thread = _make_thread([
        _message(1, "Wordle 1,234 4/6\n\n⬛🟨⬛⬛⬛\n🟩🟩🟩🟩🟩"),
        _message(2, "Wordle 1.234 X/6*"),       # failed, hard mode, dot separator
        _message(3, "wordle 987 1/6"),          # lower case, no separator
        _message(4, "I'll play later"),          # not a Result
        _message(7, "Wordle 1,234 3/6"),         # Result by someone not opted in
        _message(5, "Wordle 1,234 7/6"),         # not a valid score
    ])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc))

    thread.send.assert_awaited_once()
    text = thread.send.await_args.args[0]
    assert "<@4>" in text and "<@5>" in text and "<@6>" in text
    for member in (1, 2, 3, 7, LEFT_MEMBER):
        assert f"<@{member}>" not in text
    mentioned = {user.id for user in thread.send.await_args.kwargs["allowed_mentions"].users}
    assert mentioned == {4, 5, 6}


async def test_no_reminder_before_21_and_only_one_per_day(reminders_on):
    await _server_with_challenge([4])
    thread = _make_thread([])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 20, 59, tzinfo=timezone.utc))
    thread.send.assert_not_awaited()

    await _tick(scheduler, datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc))
    await _tick(scheduler, datetime(2026, 1, 1, 21, 1, tzinfo=timezone.utc))
    await _tick(scheduler, datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc))
    thread.send.assert_awaited_once()


async def test_late_reminder_when_the_bot_was_offline_at_21(reminders_on):
    await _server_with_challenge([4])
    thread = _make_thread([])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 22, 30, tzinfo=timezone.utc))

    thread.send.assert_awaited_once()


async def test_no_message_when_everyone_has_played(reminders_on):
    await _server_with_challenge([1])
    thread = _make_thread([_message(1, "Wordle 1,234 2/6")])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc))

    thread.send.assert_not_awaited()
    assert (await guild_config.get_guild_state(1))["reminder_date"] == "2026-01-01"


async def test_no_reminder_when_challenge_posted_after_21(reminders_on):
    await _server_with_challenge([4], posted_at=datetime(2026, 1, 1, 21, 30, tzinfo=timezone.utc))
    thread = _make_thread([])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc))

    thread.send.assert_not_awaited()


async def test_no_reminder_without_a_challenge_today(reminders_on):
    await _server_with_challenge([4], challenge_date="2026-01-01")
    thread = _make_thread([])
    scheduler = _make_scheduler(_make_reminder_bot(thread))
    scheduler._attempted = {"1": "2026-01-02"}  # today's post failed

    await _tick(scheduler, datetime(2026, 1, 2, 21, 0, tzinfo=timezone.utc))

    thread.send.assert_not_awaited()


async def test_no_reminder_on_a_stopped_server(reminders_on):
    await _server_with_challenge([4])
    await guild_config.stop_guild(1)
    thread = _make_thread([])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc))

    thread.send.assert_not_awaited()


async def test_no_reminder_when_reminders_are_not_enabled(monkeypatch):
    monkeypatch.delenv("ENABLE_REMINDERS", raising=False)
    await _server_with_challenge([4])
    thread = _make_thread([])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc))

    thread.send.assert_not_awaited()


async def test_missing_thread_in_one_server_does_not_block_another(reminders_on):
    await _server_with_challenge([4])  # server 1: thread 500 exists
    await _start_server(2, 200, "UTC", {
        "word": "CRANE", "used_words": {}, "challenge_date": "2026-01-01",
        "post_id": discord.utils.time_snowflake(MIDNIGHT), "thread_id": 404,  # gone
    })
    await guild_config.set_reminder_opt_in(2, 4, True)
    thread = _make_thread([])
    scheduler = _make_scheduler(_make_reminder_bot(thread))

    await _tick(scheduler, datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc))

    thread.send.assert_awaited_once()
