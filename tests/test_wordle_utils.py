import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from core import guild_config
from core.wordle_utils import pick_word, post_word


def _write_json_sync(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

# --- pick_word -------------------------------------------------------------

async def test_pick_word_returns_uppercased_word_from_list(word_list_file):
    theme_file = word_list_file(["apple", "grape"])

    word, used = await pick_word(theme_file)

    assert word in {"APPLE", "GRAPE"}
    assert used == [word]


async def test_pick_word_raises_on_empty_word_list(word_list_file):
    theme_file = word_list_file([])

    with pytest.raises(ValueError):
        await pick_word(theme_file)


async def test_pick_word_never_repeats_until_list_exhausted(word_list_file):
    theme_file = word_list_file(["one", "two", "three"])

    used = []
    picked = []
    for _ in range(3):
        word, used = await pick_word(theme_file, used_words=used)
        picked.append(word)

    assert sorted(picked) == ["ONE", "THREE", "TWO"]
    assert sorted(used) == ["ONE", "THREE", "TWO"]


async def test_pick_word_resets_and_reshuffles_after_exhaustion(word_list_file):
    theme_file = word_list_file(["one", "two"])

    used = ["ONE", "TWO"]  # already exhausted
    word, used = await pick_word(theme_file, used_words=used)

    assert word in {"ONE", "TWO"}
    assert used == [word]  # reset, only the newly picked word is "used"


async def test_pick_word_caches_word_list_between_calls(word_list_file):
    theme_file = word_list_file(["cached"])

    await pick_word(theme_file)

    # If a second call re-read the file it would see this new content;
    # caching means it should keep serving the original list instead.
    await asyncio.to_thread(_write_json_sync, theme_file, ["different"])

    word, _ = await pick_word(theme_file, used_words=[])
    assert word == "CACHED"


# --- post_word ---------------------------------------------------------

def _make_fake_channel(guild_id=123, thread_exc=None):
    channel = MagicMock()
    channel.guild.id = guild_id

    message = MagicMock()
    message.id = 999
    channel.send = AsyncMock(return_value=message)

    thread = MagicMock()
    thread.id = 4242
    if thread_exc is not None:
        message.create_thread = AsyncMock(side_effect=thread_exc)
    else:
        message.create_thread = AsyncMock(return_value=thread)

    return channel


def _make_fake_bot(channel):
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=channel)
    return bot


THEME = {
    "message": "Today's word is **{word}**!",
    "thread_name": "Wordle Thread {date}",
}


async def test_post_word_channel_not_found_does_not_raise():
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=None)

    await post_word(bot, 1, THEME, {"used_words": []})  # should not raise


async def test_post_word_success_updates_state_and_persists(word_list_file):
    theme = dict(THEME, file=word_list_file(["apple"]))
    channel = _make_fake_channel(guild_id=321)
    bot = _make_fake_bot(channel)
    state = {"word": None, "used_words": [], "thread_id": None}

    await post_word(bot, 55, theme, state)

    assert state["word"] == "APPLE"
    assert state["used_words"] == ["APPLE"]
    assert state["thread_id"] == 4242
    channel.send.assert_awaited_once_with("Today's word is **APPLE**!")

    persisted = await guild_config.get_guild_state(321)
    assert persisted["word"] == "APPLE"
    assert persisted["thread_id"] == 4242


async def test_post_word_persists_into_an_empty_but_present_state_dict(word_list_file):
    # An empty dict {} is a legitimate "not yet initialized" state (e.g. a
    # guild that has never run /wordle_init), distinct from state=None. It
    # must still get populated and persisted, not silently skipped just
    # because {} is falsy.
    theme = dict(THEME, file=word_list_file(["apple"]))
    channel = _make_fake_channel(guild_id=321)
    bot = _make_fake_bot(channel)
    state = {}

    await post_word(bot, 55, theme, state)

    assert state["word"] == "APPLE"
    persisted = await guild_config.get_guild_state(321)
    assert persisted["word"] == "APPLE"


async def test_post_word_empty_word_list_sends_warning_and_leaves_state_untouched(word_list_file):
    theme = dict(THEME, file=word_list_file([]))
    channel = _make_fake_channel()
    bot = _make_fake_bot(channel)
    state = {"word": None, "used_words": [], "thread_id": None}

    await post_word(bot, 1, theme, state)

    assert state["word"] is None
    channel.send.assert_awaited_once()
    assert "Couldn't load" in channel.send.await_args.args[0]


async def test_post_word_thread_creation_failure_does_not_raise(word_list_file):
    theme = dict(THEME, file=word_list_file(["apple"]))
    channel = _make_fake_channel(thread_exc=discord.HTTPException(MagicMock(status=403), "no perms"))
    bot = _make_fake_bot(channel)
    state = {"word": None, "used_words": [], "thread_id": None}

    await post_word(bot, 1, theme, state)  # should not raise

    assert state["word"] == "APPLE"
    assert state["thread_id"] is None  # thread was never created


async def test_post_word_thread_date_uses_guild_local_timezone(word_list_file):
    # Real Wordle resets at midnight in each player's own local timezone,
    # not a fixed UTC time, so the thread date should follow the guild's
    # configured timezone rather than server time.
    theme = dict(THEME, file=word_list_file(["apple"]))
    channel = _make_fake_channel()
    bot = _make_fake_bot(channel)
    state = {"word": None, "used_words": [], "thread_id": None}

    # 23:30 UTC on Jan 1 is already Jan 2 in Pacific/Auckland (UTC+13 in January).
    fixed_now = datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.astimezone(tz) if tz else fixed_now

    with patch("core.wordle_utils.datetime", FixedDatetime):
        await post_word(bot, 1, theme, state, timezone_name="Pacific/Auckland")

    thread_name = channel.send.return_value.create_thread.await_args.kwargs["name"]
    assert "Jan 02" in thread_name


async def test_post_word_falls_back_to_utc_on_unknown_timezone(word_list_file):
    theme = dict(THEME, file=word_list_file(["apple"]))
    channel = _make_fake_channel()
    bot = _make_fake_bot(channel)
    state = {"word": None, "used_words": [], "thread_id": None}

    await post_word(bot, 1, theme, state, timezone_name="Not/A_Real_Zone")  # should not raise

    assert state["word"] == "APPLE"
