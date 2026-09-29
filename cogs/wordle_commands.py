import json
import logging

import discord
import pytz
from discord import app_commands
from discord.ext import commands

from core.guild_config import (
    get_guild_entry,
    set_guild_channel,
    set_guild_state,
    set_guild_theme,
    set_guild_timezone,
    set_reminder_opt_in,
    stop_guild,
)
from core.settings import REMINDER_HOUR, reminders_enabled
from core.themes import DEFAULT_THEME, available_themes, get_theme
from core.wordle_utils import (
    challenge_posted_today,
    find_thread,
    pick_word,
    post_word,
    set_theme_used_words,
    theme_used_words,
)

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
        entry = await get_guild_entry(guild_id)
        state = entry.get("state", {})
        started = f"✅ Wordle Challenge started in <#{channel_id}>. A new Challenge posts daily at 00:00 {timezone}."
        if challenge_posted_today(state, timezone):
            await interaction.followup.send(
                f"{started} Today's Challenge was already posted, so the next one comes at 00:00.",
                ephemeral=True,
            )
            return

        theme = get_theme(entry.get("theme"))
        if await post_word(self.bot, channel_id, theme, state, timezone_name=timezone):
            await interaction.followup.send(f"{started} Today's Challenge is up!", ephemeral=True)
        else:
            await interaction.followup.send(
                f"{started} But today's Challenge could not be posted, see the message in the channel.",
                ephemeral=True,
            )

    @app_commands.command(name="wordle_theme", description="Choose the Theme for this server's Challenges")
    @app_commands.describe(theme="The Theme to use from the next Challenge")
    @app_commands.choices(
        theme=[app_commands.Choice(name=t["display_name"], value=t["name"]) for t in available_themes()]
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def theme(self, interaction: discord.Interaction, theme: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_theme invoked by guild {guild_id}: {theme.value}")

        # Today's Challenge is left alone: the Theme applies from the next one.
        await set_guild_theme(guild_id, theme.value)

        await interaction.followup.send(
            f"✅ Theme set to {get_theme(theme.value)['display_name']}. It starts with the next Challenge.",
            ephemeral=True,
        )

    @app_commands.command(name="wordle_reset", description="Reset the current Theme's used words so they can be picked again")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_reset invoked by guild {guild_id}")

        entry = await get_guild_entry(guild_id)
        theme = get_theme(entry.get("theme"))
        state = entry.get("state", {})
        set_theme_used_words(state, theme["name"], [])
        await set_guild_state(guild_id, state)

        await interaction.followup.send(
            f"✅ Used words for the {theme['display_name']} Theme have been reset. "
            "Its previously used words can be picked again.",
            ephemeral=True,
        )

    @app_commands.command(name="wordle_replace", description="Replace today's Starter Word if it is unplayable")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def replace(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        logger.info(f"/wordle_replace invoked by guild {guild_id}")

        entry = await get_guild_entry(guild_id)
        state = entry.get("state", {})
        if not challenge_posted_today(state, entry.get("timezone", "UTC")):
            await interaction.followup.send(
                "❌ There is no Challenge today, so there is no Starter Word to replace.", ephemeral=True
            )
            return

        thread = await find_thread(self.bot, state.get("thread_id"))
        if thread is None:
            await interaction.followup.send(
                "❌ I can't find today's Challenge thread, so the Starter Word was not replaced.",
                ephemeral=True,
            )
            return

        # A Replacement stays in the Theme today's Challenge was posted with,
        # even if a Server Admin has picked a different Theme since.
        theme = get_theme(state.get("theme", DEFAULT_THEME))
        old_word = state.get("word")
        try:
            new_word, used = await pick_word(
                theme["file"], used_words=theme_used_words(state, theme["name"])
            )
        except (ValueError, FileNotFoundError, json.JSONDecodeError):
            logger.exception(f"Failed to pick a replacement word for guild {guild_id}")
            await interaction.followup.send(
                "❌ Couldn't load the word list, so the Starter Word was not replaced.", ephemeral=True
            )
            return

        try:
            await thread.send(f"🔁 Replacement: today's Starter Word is now **{new_word}** (replaces {old_word}).")
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ I can't post in today's Challenge thread, so the Starter Word was not replaced.",
                ephemeral=True,
            )
            return

        # The Replacement counts from here: the same Challenge, a new Starter Word.
        state["word"] = new_word
        set_theme_used_words(state, theme["name"], used)
        await set_guild_state(guild_id, state)

        try:
            post = await thread.parent.fetch_message(state["post_id"])
            await post.edit(
                content=f"~~{theme['message'].format(word=old_word)}~~\n"
                f"🔁 Replaced: today's Starter Word is **{new_word}**."
            )
        except (discord.HTTPException, KeyError, AttributeError):
            logger.warning(f"Could not edit the Challenge post for guild {guild_id}", exc_info=True)

        await interaction.followup.send(
            f"✅ Starter Word replaced: {old_word} is now {new_word}.", ephemeral=True
        )

    @app_commands.command(name="wordle_remind", description="Get pinged at 21:00 if you haven't posted your Result")
    @app_commands.describe(setting="Turn your Reminder on or off for this server")
    @app_commands.choices(
        setting=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")]
    )
    @app_commands.guild_only()
    async def remind(self, interaction: discord.Interaction, setting: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        if not reminders_enabled():
            await interaction.followup.send("❌ Reminders are not enabled on this bot.", ephemeral=True)
            return

        opted_in = setting.value == "on"
        await set_reminder_opt_in(interaction.guild.id, interaction.user.id, opted_in)

        if opted_in:
            message = (
                f"🔔 You're opted in. If you haven't posted your Result in today's Challenge thread by "
                f"{REMINDER_HOUR}:00 server time, I'll ping you there. Use `/wordle_remind off` to stop."
            )
        else:
            message = "🔕 You're opted out of Reminders on this server."
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="wordle_status", description="Show this server's current Wordle configuration")
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        entry = await get_guild_entry(guild_id)
        channel_id = entry.get("channel_id")
        tz_name = entry.get("timezone", "UTC")
        state = entry.get("state", {})
        theme = get_theme(entry.get("theme"))
        current_word = state.get("word") if challenge_posted_today(state, tz_name) else None
        used_count = len(theme_used_words(state, theme["name"]))

        if channel_id:
            lines = [
                f"📍 Posting channel: <#{channel_id}>",
                f"⏰ Daily Challenge: 00:00 {tz_name}",
            ]
        else:
            lines = ["⏸️ Stopped: no daily Challenges (use /wordle_start to start)"]
        lines += [
            f"🎨 Theme: {theme['display_name']}",
            f"📝 Today's Starter Word: {current_word}" if current_word else "📝 Today's Starter Word: not posted yet",
            f"📚 Words used so far ({theme['display_name']}): {used_count}",
        ]
        if reminders_enabled():
            opted_in = len(entry.get("reminder_members", []))
            lines.append(f"🔔 Reminders: on at {REMINDER_HOUR}:00, {opted_in} member(s) opted in")
        else:
            lines.append("🔕 Reminders: not enabled on this bot")

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