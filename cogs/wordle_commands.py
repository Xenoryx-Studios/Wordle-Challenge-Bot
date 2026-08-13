import logging

import discord
import pytz
from discord import app_commands
from discord.ext import commands

from core.guild_config import (
    clear_guild_schedule,
    get_guild_entry,
    get_guild_state,
    get_guild_timezone,
    set_guild_channel,
    set_guild_schedule,
    set_guild_state,
)
from core.themes import THEMES
from core.wordle_utils import post_word

logger = logging.getLogger("wordle-bot")

RULES_MESSAGE = """**Wordle Challenge Rules**
1. Each day has a starter word.
2. Use it as your first guess in Wordle.
3. Try to solve in as few guesses as possible.
4. Post your results in the channel using the Wordle share squares.
Have fun!"""

class WordleCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            message = "❌ You need the **Manage Server** permission to use this command."
        elif isinstance(error, app_commands.NoPrivateMessage):
            message = "❌ This command can only be used in a server."
        else:
            logger.exception("Unhandled app command error", exc_info=error)
            message = "❌ Something went wrong running that command."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="wordle_init", description="Initialize today's Wordle manually")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def initialize(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = interaction.channel.id
        logger.info(f"/wordle_init invoked by guild {guild_id}")

        permissions = interaction.channel.permissions_for(interaction.guild.me)
        if not permissions.send_messages:
            await interaction.followup.send(
                "❌ I don't have permission to send messages in this channel. "
                "Please grant me Send Messages here and try again.",
                ephemeral=True,
            )
            return

        # Preserve previously used words so re-running this command doesn't
        # reopen already-used words for re-selection.
        existing_state = await get_guild_state(guild_id)
        state = {
            "word": None,
            "used_words": existing_state.get("used_words", []),
            "thread_id": None,
        }

        # Save channel and initial state
        await set_guild_channel(guild_id, channel_id)
        await set_guild_state(guild_id, state)

        rules_msg = await interaction.channel.send(RULES_MESSAGE)
        try:
            await rules_msg.pin()
        except discord.Forbidden:
            logger.warning(f"Missing permissions to pin messages in guild {guild_id}")

        theme = THEMES.get("default")
        timezone_name = await get_guild_timezone(guild_id)
        await post_word(self.bot, channel_id, theme, state, timezone_name=timezone_name)

        await interaction.followup.send("Wordle initialized and rules posted!", ephemeral=True)

    @app_commands.command(name="wordle_schedule", description="Set daily Wordle post time for this server")
    @app_commands.describe(hour="Hour (0-23)", minute="Minute (0-59)", timezone="IANA timezone name")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def wordle_schedule(
        self,
        interaction: discord.Interaction,
        hour: app_commands.Range[int, 0, 23],
        minute: app_commands.Range[int, 0, 59],
        timezone: str,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_schedule invoked by guild {guild_id}")

        if timezone not in pytz.all_timezones:
            await interaction.followup.send("❌ Invalid timezone!", ephemeral=True)
            return

        await set_guild_schedule(guild_id, hour, minute, timezone)
        await set_guild_channel(guild_id, interaction.channel.id)

        await interaction.followup.send(
            f"✅ Wordle will post daily at {hour:02d}:{minute:02d} {timezone} in this channel.",
            ephemeral=True
        )

    @app_commands.command(name="wordle_reset", description="Reset the used-words history so old words can be picked again")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_reset invoked by guild {guild_id}")

        state = await get_guild_state(guild_id)
        state["used_words"] = []
        await set_guild_state(guild_id, state)

        await interaction.followup.send(
            "✅ Used-words history has been reset. Previously used words can be picked again.",
            ephemeral=True,
        )

    @app_commands.command(name="wordle_skip", description="Post a new Wordle word right now, without reposting the rules")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = interaction.channel.id
        logger.info(f"/wordle_skip invoked by guild {guild_id}")

        permissions = interaction.channel.permissions_for(interaction.guild.me)
        if not permissions.send_messages:
            await interaction.followup.send(
                "❌ I don't have permission to send messages in this channel. "
                "Please grant me Send Messages here and try again.",
                ephemeral=True,
            )
            return

        state = await get_guild_state(guild_id)
        theme = THEMES.get("default")
        timezone_name = await get_guild_timezone(guild_id)
        await post_word(self.bot, channel_id, theme, state, timezone_name=timezone_name)

        await interaction.followup.send("✅ New Wordle word posted!", ephemeral=True)

    @app_commands.command(name="wordle_status", description="Show this server's current Wordle configuration")
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        entry = await get_guild_entry(guild_id)
        channel_id = entry.get("channel_id")
        hour = entry.get("hour")
        minute = entry.get("minute")
        tz_name = entry.get("timezone")
        state = entry.get("state", {})
        current_word = state.get("word")
        used_count = len(state.get("used_words", []))

        lines = [
            f"📍 Posting channel: <#{channel_id}>" if channel_id else "📍 Posting channel: not set",
            f"⏰ Daily schedule: {hour:02d}:{minute:02d} {tz_name}"
            if hour is not None and minute is not None and tz_name
            else "⏰ Daily schedule: not set (use /wordle_schedule)",
            f"📝 Today's word: {current_word}" if current_word else "📝 Today's word: not posted yet",
            f"📚 Words used so far: {used_count}",
        ]

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(name="wordle_stop", description="Disable automatic daily Wordle posting for this server")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_stop invoked by guild {guild_id}")

        await clear_guild_schedule(guild_id)

        await interaction.followup.send(
            "✅ Automatic daily posting has been disabled. Word history is preserved — "
            "use /wordle_schedule to re-enable.",
            ephemeral=True,
        )

    @app_commands.command(name="wordle_help", description="Show the Wordle Challenge rules")
    async def show_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(RULES_MESSAGE)

async def setup(bot: commands.Bot):
    await bot.add_cog(WordleCommands(bot))