import logging

import discord
import pytz
from discord import app_commands
from discord.ext import commands

from core.guild_config import (
    get_guild_entry,
    get_guild_state,
    get_guild_timezone,
    set_guild_channel,
    set_guild_state,
    set_guild_timezone,
    stop_guild,
)
from core.themes import THEMES
from core.wordle_utils import challenge_posted_today, post_word

logger = logging.getLogger("wordle-bot")

RULES_MESSAGE = """**Wordle Challenge Rules**
1. Each day has a starter word.
2. Use it as your first guess in Wordle.
3. Try to solve in as few guesses as possible.
4. Post your Result (the Wordle share squares) in the Challenge thread.
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

    @app_commands.command(name="wordle_start", description="Start daily Wordle Challenges in this channel")
    @app_commands.describe(timezone="IANA timezone name, e.g. America/Toronto")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start(self, interaction: discord.Interaction, timezone: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = interaction.channel.id
        logger.info(f"/wordle_start invoked by guild {guild_id}")

        if timezone not in pytz.all_timezones:
            await interaction.followup.send(
                "❌ Invalid timezone! Use an IANA name such as `America/Toronto`.", ephemeral=True
            )
            return

        permissions = interaction.channel.permissions_for(interaction.guild.me)
        if not permissions.send_messages:
            await interaction.followup.send(
                "❌ I don't have permission to send messages in this channel. "
                "Please grant me Send Messages here and try again.",
                ephemeral=True,
            )
            return

        await set_guild_channel(guild_id, channel_id)
        await set_guild_timezone(guild_id, timezone)

        rules_msg = await interaction.channel.send(RULES_MESSAGE)
        try:
            await rules_msg.pin()
        except discord.Forbidden:
            logger.warning(f"Missing permissions to pin messages in guild {guild_id}")

        # Existing state (Used Words in particular) is kept, so restarting a
        # Stopped server does not reopen old Starter Words.
        state = await get_guild_state(guild_id)
        started = f"✅ Wordle Challenge started in <#{channel_id}>. A new Challenge posts daily at 00:00 {timezone}."
        if challenge_posted_today(state, timezone):
            await interaction.followup.send(
                f"{started} Today's Challenge was already posted, so the next one comes at 00:00.",
                ephemeral=True,
            )
            return

        theme = THEMES.get("default")
        if await post_word(self.bot, channel_id, theme, state, timezone_name=timezone):
            await interaction.followup.send(f"{started} Today's Challenge is up!", ephemeral=True)
        else:
            await interaction.followup.send(
                f"{started} But today's Challenge could not be posted, see the message in the channel.",
                ephemeral=True,
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
        tz_name = entry.get("timezone", "UTC")
        state = entry.get("state", {})
        current_word = state.get("word") if challenge_posted_today(state, tz_name) else None
        used_count = len(state.get("used_words", []))

        if channel_id:
            lines = [
                f"📍 Posting channel: <#{channel_id}>",
                f"⏰ Daily Challenge: 00:00 {tz_name}",
            ]
        else:
            lines = ["⏸️ Stopped: no daily Challenges (use /wordle_start to start)"]
        lines += [
            f"📝 Today's Starter Word: {current_word}" if current_word else "📝 Today's Starter Word: not posted yet",
            f"📚 Words used so far: {used_count}",
        ]

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(name="wordle_stop", description="Stop daily Wordle Challenges for this server")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_stop invoked by guild {guild_id}")

        await stop_guild(guild_id)

        await interaction.followup.send(
            "✅ Daily Challenges are stopped. Used words are kept: "
            "use /wordle_start to start again.",
            ephemeral=True,
        )

    @app_commands.command(name="wordle_help", description="Show the Wordle Challenge rules")
    async def show_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(RULES_MESSAGE)

async def setup(bot: commands.Bot):
    await bot.add_cog(WordleCommands(bot))