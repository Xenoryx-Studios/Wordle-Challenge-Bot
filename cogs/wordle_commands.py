import discord
from discord.ext import commands
from discord import app_commands
import logging
import pytz
from core.guild_config import (
    set_guild_state, set_guild_channel, set_guild_schedule
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

    @app_commands.command(name="wordle_init", description="Initialize today's Wordle manually")
    async def initialize(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = interaction.channel.id
        logger.info(f"/wordle_init invoked by guild {guild_id}")
        state = {"word": None, "used_words": [], "thread_id": None}
        
        # Save channel and initial state
        set_guild_channel(guild_id, channel_id)
        set_guild_state(guild_id, state)

        rules_msg = await interaction.channel.send(RULES_MESSAGE)
        try:
            await rules_msg.pin()
        except discord.Forbidden:
            logger.warning(f"Missing permissions to pin messages in guild {guild_id}")

        theme = THEMES.get("default")
        await post_word(self.bot, channel_id, theme, state)

        await interaction.followup.send("Wordle initialized and rules posted!", ephemeral=True)

    @app_commands.command(name="wordle_schedule", description="Set daily Wordle post time for this server")
    @app_commands.describe(hour="Hour (0-23)", minute="Minute (0-59)", timezone="IANA timezone name")
    async def wordle_schedule(self, interaction: discord.Interaction, hour: int, minute: int, timezone: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_schedule invoked by guild {guild_id}")

        if timezone not in pytz.all_timezones:
            await interaction.followup.send("❌ Invalid timezone!", ephemeral=True)
            return

        set_guild_schedule(guild_id, hour, minute, timezone)
        set_guild_channel(guild_id, interaction.channel.id)

        await interaction.followup.send(
            f"✅ Wordle will post daily at {hour:02d}:{minute:02d} {timezone} in this channel.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(WordleCommands(bot))