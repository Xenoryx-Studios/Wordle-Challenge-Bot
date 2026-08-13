import logging
import os
import sys

import discord
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("wordle-bot")

logger.info("Starting Wordle Bot...")

intents = discord.Intents.default()


class WordleBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extension("cogs.scheduler")
        await self.load_extension("cogs.wordle_commands")
        await self.tree.sync()


bot = WordleBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} ({bot.user.id})")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    logger.error("DISCORD_TOKEN environment variable is not set. Exiting.")
    sys.exit(1)

bot.run(TOKEN)