from unittest.mock import AsyncMock, MagicMock

from cogs.wordle_commands import WordleCommands
from core import guild_config


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
    message.pin = AsyncMock()
    message.create_thread = AsyncMock(return_value=MagicMock(id=999))
    interaction.channel.send = AsyncMock(return_value=message)

    return interaction


async def test_wordle_init_blocks_when_bot_cannot_send_messages():
    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(can_send=False)

    await cog.initialize.callback(cog, interaction)

    interaction.followup.send.assert_awaited_once()
    sent_message = interaction.followup.send.await_args.args[0]
    assert "permission" in sent_message.lower()
    interaction.channel.send.assert_not_awaited()

    # Nothing should have been persisted since we bailed out early.
    assert await guild_config.load_guild_config() == {}


async def test_wordle_init_proceeds_when_permission_granted():
    interaction = _make_interaction(guild_id=42, channel_id=7, can_send=True)
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=interaction.channel)
    cog = WordleCommands(bot)

    await cog.initialize.callback(cog, interaction)

    assert interaction.channel.send.await_count == 2  # rules message + word message
    interaction.followup.send.assert_awaited_once_with(
        "Wordle initialized and rules posted!", ephemeral=True
    )

    state = await guild_config.get_guild_state(42)
    assert state["word"] is not None


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
    assert "not set" in report
    assert "not posted yet" in report


async def test_wordle_status_reports_configured_server():
    await guild_config.set_guild_channel(1, 123)
    await guild_config.set_guild_schedule(1, 9, 30, "America/Toronto")
    await guild_config.set_guild_state(1, {"word": "CRANE", "used_words": ["CRANE", "SLATE"]})

    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(guild_id=1)

    await cog.status.callback(cog, interaction)

    report = interaction.followup.send.await_args.args[0]
    assert "<#123>" in report
    assert "09:30 America/Toronto" in report
    assert "CRANE" in report
    assert "Words used so far: 2" in report


async def test_wordle_stop_clears_schedule_but_keeps_word_history():
    await guild_config.set_guild_channel(1, 123)
    await guild_config.set_guild_schedule(1, 9, 30, "America/Toronto")
    await guild_config.set_guild_state(1, {"word": "CRANE", "used_words": ["CRANE"]})

    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction(guild_id=1)

    await cog.stop.callback(cog, interaction)

    entry = await guild_config.get_guild_entry(1)
    assert "channel_id" not in entry
    assert "hour" not in entry
    assert entry["state"]["used_words"] == ["CRANE"]
    interaction.followup.send.assert_awaited_once()
    assert "disabled" in interaction.followup.send.await_args.args[0].lower()


async def test_wordle_help_sends_rules_publicly():
    from cogs.wordle_commands import RULES_MESSAGE

    bot = MagicMock()
    cog = WordleCommands(bot)
    interaction = _make_interaction()

    await cog.show_help.callback(cog, interaction)

    interaction.response.send_message.assert_awaited_once_with(RULES_MESSAGE)
