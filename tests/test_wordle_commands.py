from unittest.mock import AsyncMock, MagicMock

from cogs.wordle_commands import RULES_MESSAGE, WordleCommands
from core import guild_config
from core.wordle_utils import local_today


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
    assert state["used_words"][:2] == ["CRANE", "SLATE"]
    assert len(state["used_words"]) == 3  # today's new Starter Word added
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
    assert state["used_words"] == []
    assert state["word"] == "CRANE"  # untouched
    assert state["thread_id"] == 55  # untouched
    interaction.followup.send.assert_awaited_once()
    assert "reset" in interaction.followup.send.await_args.args[0].lower()


async def test_wordle_skip_blocks_when_bot_cannot_send_messages():
    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(can_send=False)

    await cog.skip.callback(cog, interaction)

    interaction.followup.send.assert_awaited_once()
    assert "permission" in interaction.followup.send.await_args.args[0].lower()
    interaction.channel.send.assert_not_awaited()


async def test_wordle_skip_posts_a_word_without_reposting_rules():
    interaction = _make_interaction(guild_id=42, channel_id=7, can_send=True)
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=interaction.channel)
    cog = WordleCommands(bot)

    await cog.skip.callback(cog, interaction)

    assert interaction.channel.send.await_count == 1  # word message only, no rules repost
    interaction.followup.send.assert_awaited_once_with("✅ New Wordle word posted!", ephemeral=True)

    state = await guild_config.get_guild_state(42)
    assert state["word"] is not None


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
    assert "Words used so far: 2" in report


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
