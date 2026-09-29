from unittest.mock import AsyncMock, MagicMock

import discord

from cogs.wordle_commands import RULES_MESSAGE, WordleCommands
from core import guild_config
from core.themes import get_theme
from core.wordle_utils import _get_words, local_today


def _make_interaction(guild_id=1, channel_id=2, can_send=True):
    interaction = MagicMock()
    interaction.guild.id = guild_id
    interaction.channel.id = channel_id
    interaction.channel.guild = interaction.guild  # same guild, as in real Discord
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=True)
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()

    permissions = MagicMock()
    permissions.send_messages = can_send
    interaction.channel.permissions_for = MagicMock(return_value=permissions)

    message = MagicMock()
    message.id = 555
    message.pin = AsyncMock()
    message.create_thread = AsyncMock(return_value=MagicMock(id=999))
    interaction.channel.send = AsyncMock(return_value=message)

    return interaction


def _make_cog(interaction):
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=interaction.channel)
    return WordleCommands(bot)


async def test_wordle_start_rejects_invalid_timezone():
    interaction = _make_interaction()
    cog = _make_cog(interaction)

    await cog.start.callback(cog, interaction, "Not/A_Real_Zone")

    assert "invalid timezone" in interaction.followup.send.await_args.args[0].lower()
    interaction.channel.send.assert_not_awaited()
    assert await guild_config.load_guild_config() == {}


async def test_wordle_start_blocks_when_bot_cannot_send_messages():
    interaction = _make_interaction(can_send=False)
    cog = _make_cog(interaction)

    await cog.start.callback(cog, interaction, "UTC")

    interaction.followup.send.assert_awaited_once()
    assert "permission" in interaction.followup.send.await_args.args[0].lower()
    interaction.channel.send.assert_not_awaited()
    # Nothing should have been persisted since we bailed out early.
    assert await guild_config.load_guild_config() == {}


async def test_wordle_start_saves_settings_posts_rules_and_todays_challenge():
    interaction = _make_interaction(guild_id=42, channel_id=7)
    cog = _make_cog(interaction)

    await cog.start.callback(cog, interaction, "America/Toronto")

    entry = await guild_config.get_guild_entry(42)
    assert entry["channel_id"] == 7
    assert entry["timezone"] == "America/Toronto"
    assert "hour" not in entry
    assert interaction.channel.send.await_args_list[0].args[0] == RULES_MESSAGE
    interaction.channel.send.return_value.pin.assert_awaited()
    assert interaction.channel.send.await_count == 2  # rules + Challenge post
    assert entry["state"]["word"] is not None
    assert entry["state"]["challenge_date"] == local_today("America/Toronto")
    reply = interaction.followup.send.await_args.args[0]
    assert "00:00 America/Toronto" in reply


async def test_wordle_start_restarts_stopped_server_and_keeps_used_words():
    await guild_config.set_guild_state(42, {"word": "CRANE", "used_words": ["CRANE", "SLATE"], "challenge_date": "2020-01-01"})
    interaction = _make_interaction(guild_id=42, channel_id=7)
    cog = _make_cog(interaction)

    await cog.start.callback(cog, interaction, "UTC")

    state = await guild_config.get_guild_state(42)
    used = state["used_words"]["default"]
    assert used[:2] == ["CRANE", "SLATE"]
    assert len(used) == 3  # today's new Starter Word added
    assert state["word"] not in {"CRANE", "SLATE"}


async def test_wordle_start_does_not_post_a_second_challenge_today():
    today = local_today("UTC")
    await guild_config.set_guild_channel(42, 7)
    await guild_config.set_guild_state(42, {"word": "CRANE", "used_words": ["CRANE"], "challenge_date": today})
    interaction = _make_interaction(guild_id=42, channel_id=8)
    cog = _make_cog(interaction)

    await cog.start.callback(cog, interaction, "UTC")

    assert interaction.channel.send.await_count == 1  # rules only
    entry = await guild_config.get_guild_entry(42)
    assert entry["channel_id"] == 8  # moved for the next Challenge
    assert entry["state"]["word"] == "CRANE"
    assert "already posted" in interaction.followup.send.await_args.args[0]


async def test_old_setup_commands_are_gone():
    names = {command.name for command in WordleCommands(MagicMock()).get_app_commands()}
    assert "wordle_start" in names
    assert not names & {"wordle_init", "wordle_schedule"}


async def test_wordle_reset_clears_used_words_but_keeps_current_word():
    await guild_config.set_guild_state(1, {"word": "CRANE", "used_words": ["CRANE", "SLATE"], "thread_id": 55})

    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(guild_id=1)

    await cog.reset.callback(cog, interaction)

    state = await guild_config.get_guild_state(1)
    assert state["used_words"] == {"default": []}
    assert state["word"] == "CRANE"  # untouched
    assert state["thread_id"] == 55  # untouched
    interaction.followup.send.assert_awaited_once()
    assert "reset" in interaction.followup.send.await_args.args[0].lower()


def _make_replace_setup(guild_id=1, challenge_today=True, thread_found=True, thread_send_exc=None, edit_exc=None):
    """A server whose Challenge (post 500, thread 500) posted today with Starter Word CRANE."""
    thread = MagicMock()
    thread.send = AsyncMock(side_effect=thread_send_exc)
    post = MagicMock()
    post.edit = AsyncMock(side_effect=edit_exc)
    thread.parent.fetch_message = AsyncMock(return_value=post)

    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=thread if thread_found else None)
    not_found = discord.NotFound(MagicMock(status=404), "unknown channel")
    bot.fetch_channel = AsyncMock(side_effect=not_found)

    state = {
        "word": "CRANE",
        "used_words": ["SLATE", "CRANE"],
        "thread_id": 500,
        "post_id": 500,
        "challenge_date": local_today("UTC") if challenge_today else "2020-01-01",
    }
    return bot, thread, post, state


async def _run_replace(bot, state, guild_id=1):
    await guild_config.set_guild_channel(guild_id, 7)
    await guild_config.set_guild_timezone(guild_id, "UTC")
    await guild_config.set_guild_state(guild_id, state)
    cog = WordleCommands(bot)
    interaction = _make_interaction(guild_id=guild_id, channel_id=99)  # any channel
    await cog.replace.callback(cog, interaction)
    reply = interaction.followup.send.await_args.args[0]
    return reply, await guild_config.get_guild_state(guild_id)


async def test_wordle_replace_posts_new_word_in_the_existing_thread():
    bot, thread, post, state = _make_replace_setup()

    reply, saved = await _run_replace(bot, state)

    new_word = saved["word"]
    assert new_word not in {"CRANE", "SLATE"}
    thread.send.assert_awaited_once()
    assert new_word in thread.send.await_args.args[0]
    assert "CRANE" in thread.send.await_args.args[0]
    thread.parent.fetch_message.assert_awaited_once_with(500)
    edited = post.edit.await_args.kwargs["content"]
    assert "~~" in edited and new_word in edited
    assert saved["used_words"] == {"default": ["SLATE", "CRANE", new_word]}
    assert (saved["thread_id"], saved["post_id"], saved["challenge_date"]) == (500, 500, state["challenge_date"])
    assert "replaced" in reply.lower()


async def test_wordle_replace_finds_archived_thread_via_fetch():
    bot, thread, _, state = _make_replace_setup(thread_found=False)
    bot.fetch_channel = AsyncMock(return_value=thread)

    _, saved = await _run_replace(bot, state)

    bot.fetch_channel.assert_awaited_once_with(500)
    assert saved["word"] != "CRANE"


async def test_wordle_replace_refuses_when_no_challenge_today():
    bot, thread, _, state = _make_replace_setup(challenge_today=False)

    reply, saved = await _run_replace(bot, state)

    assert "no challenge today" in reply.lower()
    thread.send.assert_not_awaited()
    assert saved["word"] == "CRANE"


async def test_wordle_replace_refuses_when_thread_is_gone():
    bot, _, _, state = _make_replace_setup(thread_found=False)

    reply, saved = await _run_replace(bot, state)

    assert "thread" in reply.lower() and "not replaced" in reply.lower()
    assert saved == state


async def test_wordle_replace_refuses_when_bot_cannot_post_in_thread():
    bot, _, post, state = _make_replace_setup(
        thread_send_exc=discord.Forbidden(MagicMock(status=403), "missing access")
    )

    reply, saved = await _run_replace(bot, state)

    assert "not replaced" in reply.lower()
    post.edit.assert_not_awaited()
    assert saved == state


async def test_wordle_replace_still_counts_when_editing_the_post_fails():
    bot, thread, _, state = _make_replace_setup(
        edit_exc=discord.Forbidden(MagicMock(status=403), "cannot edit")
    )

    reply, saved = await _run_replace(bot, state)

    thread.send.assert_awaited_once()
    assert saved["word"] != "CRANE"
    assert "replaced" in reply.lower()


async def test_wordle_skip_is_gone():
    names = {command.name for command in WordleCommands(MagicMock()).get_app_commands()}
    assert "wordle_replace" in names
    assert "wordle_skip" not in names


async def test_wordle_status_reports_unconfigured_server():
    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(guild_id=1)

    await cog.status.callback(cog, interaction)

    report = interaction.followup.send.await_args.args[0]
    assert "Stopped" in report
    assert "/wordle_start" in report
    assert "not posted yet" in report


async def test_wordle_status_reports_configured_server():
    await guild_config.set_guild_channel(1, 123)
    await guild_config.set_guild_timezone(1, "America/Toronto")
    await guild_config.set_guild_state(
        1,
        {"word": "CRANE", "used_words": ["CRANE", "SLATE"], "challenge_date": local_today("America/Toronto")},
    )

    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(guild_id=1)

    await cog.status.callback(cog, interaction)

    report = interaction.followup.send.await_args.args[0]
    assert "<#123>" in report
    assert "00:00 America/Toronto" in report
    assert "Stopped" not in report
    assert "CRANE" in report
    assert "Theme: Default" in report
    assert "Words used so far (Default): 2" in report


async def test_wordle_stop_clears_schedule_but_keeps_word_history():
    await guild_config.set_guild_channel(1, 123)
    await guild_config.set_guild_timezone(1, "America/Toronto")
    await guild_config.set_guild_state(1, {"word": "CRANE", "used_words": ["CRANE"]})

    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(guild_id=1)

    await cog.stop.callback(cog, interaction)

    entry = await guild_config.get_guild_entry(1)
    assert "channel_id" not in entry
    assert entry["state"]["used_words"] == ["CRANE"]
    interaction.followup.send.assert_awaited_once()
    assert "stopped" in interaction.followup.send.await_args.args[0].lower()


async def test_wordle_help_sends_rules_publicly():
    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction()

    await cog.show_help.callback(cog, interaction)

    interaction.response.send_message.assert_awaited_once_with(RULES_MESSAGE)


# --- Themes ---------------------------------------------------------------

async def test_wordle_theme_saves_selection_and_leaves_todays_challenge_alone():
    from discord import app_commands

    today_state = {"word": "CRANE", "used_words": {"default": ["CRANE"]}, "theme": "default",
                   "challenge_date": local_today("UTC")}
    await guild_config.set_guild_channel(1, 7)
    await guild_config.set_guild_state(1, today_state)
    cog = WordleCommands(MagicMock())
    interaction = _make_interaction(guild_id=1)

    await cog.theme.callback(cog, interaction, app_commands.Choice(name="Halloween", value="halloween"))

    entry = await guild_config.get_guild_entry(1)
    assert entry["theme"] == "halloween"
    assert entry["state"] == today_state
    interaction.channel.send.assert_not_awaited()
    assert "next Challenge" in interaction.followup.send.await_args.args[0]


async def test_wordle_theme_works_on_a_stopped_server():
    from discord import app_commands

    cog = WordleCommands(MagicMock())
    interaction = _make_interaction(guild_id=1)

    await cog.theme.callback(cog, interaction, app_commands.Choice(name="Christmas", value="christmas"))

    assert (await guild_config.get_guild_entry(1)) == {"theme": "christmas"}


async def test_wordle_theme_dropdown_lists_every_theme_with_words():
    command = next(c for c in WordleCommands(MagicMock()).get_app_commands() if c.name == "wordle_theme")
    values = {choice.value for choice in command.parameters[0].choices}
    assert values == {"default", "halloween", "christmas"}


async def test_wordle_reset_clears_only_the_current_themes_used_words():
    await guild_config.set_guild_theme(1, "halloween")
    await guild_config.set_guild_state(1, {"used_words": {"default": ["CRANE"], "halloween": ["GHOST", "WITCH"]}})
    cog = WordleCommands(MagicMock())
    interaction = _make_interaction(guild_id=1)

    await cog.reset.callback(cog, interaction)

    state = await guild_config.get_guild_state(1)
    assert state["used_words"] == {"default": ["CRANE"], "halloween": []}
    assert "Halloween" in interaction.followup.send.await_args.args[0]


async def test_wordle_status_shows_theme_and_its_used_words_count():
    await guild_config.set_guild_channel(1, 123)
    await guild_config.set_guild_theme(1, "halloween")
    await guild_config.set_guild_state(1, {"used_words": {"default": ["A", "B", "C"], "halloween": ["GHOST"]}})
    cog = WordleCommands(MagicMock())
    interaction = _make_interaction(guild_id=1)

    await cog.status.callback(cog, interaction)

    report = interaction.followup.send.await_args.args[0]
    assert "Theme: Halloween" in report
    assert "Words used so far (Halloween): 1" in report


async def test_wordle_replace_stays_in_todays_challenge_theme_after_a_theme_change():
    bot, _, _, state = _make_replace_setup()
    state.update(word="GHOST", theme="halloween", used_words={"halloween": ["GHOST"], "default": ["CRANE"]})
    await guild_config.set_guild_theme(1, "christmas")  # changed mid-day

    _, saved = await _run_replace(bot, state)

    halloween_words = await _get_words(get_theme("halloween")["file"])
    assert saved["word"] in halloween_words
    assert saved["used_words"]["halloween"] == ["GHOST", saved["word"]]
    assert saved["used_words"]["default"] == ["CRANE"]
    assert "christmas" not in saved["used_words"]
