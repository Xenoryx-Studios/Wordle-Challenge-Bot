import discord
from discord.ext import commands
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("wordle-bot")

logger.info("Starting Wordle Bot...")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.load_extension("cogs.scheduler")
    await bot.load_extension("cogs.wordle_commands")
    await bot.tree.sync()
    logger.info(f"Logged in as {bot.user} ({bot.user.id})")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)