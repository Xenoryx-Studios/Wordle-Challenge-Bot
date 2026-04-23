import discord
from discord.ext import tasks, commands
from datetime import datetime
import pytz
from core.guild_config import load_guild_config, save_guild_config
from core.themes import THEMES
from core.wordle_utils import post_word

class Scheduler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_task.start()

    def cog_unload(self):
        self.daily_task.cancel()

    @tasks.loop(seconds=60)
    async def daily_task(self):
        await self.bot.wait_until_ready()
        guild_configs = load_guild_config()
        theme = THEMES.get("default")

        now_utc = datetime.utcnow()
        for guild_id_str, data in guild_configs.items():
            channel_id = data.get("channel_id")
            hour = data.get("hour", 0)
            minute = data.get("minute", 0)
            tz_name = data.get("timezone", "UTC")
            state = data.get("state", {"word": None, "used_words": [], "thread_id": None})

            if not channel_id:
                continue

            tz = pytz.timezone(tz_name)
            now_local = now_utc.replace(tzinfo=pytz.utc).astimezone(tz)

            if now_local.hour == hour and now_local.minute == minute:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                try:
                    await post_word(self.bot, channel_id, theme, state)
                    # Save updated state
                    data["state"] = state
                    save_guild_config(guild_configs)
                except discord.Forbidden:
                    print(f"Missing permissions for {channel_id} in guild {guild_id_str}")
                except Exception as e:
                    print(f"Error posting in {channel_id}: {e}")

    @daily_task.before_loop
    async def before_daily_task(self):
        await self.bot.wait_until_ready()

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(Scheduler(bot))