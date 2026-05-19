import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

import db.database as db
from config import GAIN_TIP, TIMEZONE, DM_NOTIFY_THRESHOLD, TIP_SOUND_PATH, TIP_REPORT_CHAR_LIMIT
from utils.score_utils import get_tier, check_tier_change
from utils.voice import play_voice_announcement

TZ = ZoneInfo(TIMEZONE)


class Tipping(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="tip", description="Commend a user and raise their behaviour score by 100")
    @app_commands.describe(
        user="The user to commend",
        note=f"Note attached to the tip (max {TIP_REPORT_CHAR_LIMIT} characters)",
    )
    async def tip(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        note: str,
    ) -> None:
        note = note.strip()
        if len(note) > TIP_REPORT_CHAR_LIMIT:
            await interaction.response.send_message(f"Note cannot exceed {TIP_REPORT_CHAR_LIMIT} characters.", ephemeral=True)
            return
        if not note:
            await interaction.response.send_message("Note cannot be empty.", ephemeral=True)
            return

        tipper_id = interaction.user.id
        recipient_id = user.id
        guild_id = interaction.guild_id
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        if user.bot:
            await interaction.response.send_message("You cannot tip bots.")
            return
        if tipper_id == recipient_id:
            await interaction.response.send_message("You cannot tip yourself.")
            return

        tipper = await db.get_or_create_user(tipper_id, guild_id)
        _, _, tip_limit = get_tier(tipper["score"])
        tracking = await db.get_today_tracking(tipper_id, guild_id, today)

        if tracking["tips_given"] >= tip_limit:
            await interaction.response.send_message(
                f"You have used all **{tip_limit}** of your daily tips. They reset at midnight (GMT+2).",
            )
            return

        await db.get_or_create_user(recipient_id, guild_id)
        reason = f"Tip from {interaction.user.display_name}: {note}"
        old, new = await db.apply_score_delta(recipient_id, guild_id, GAIN_TIP, reason, "tip")
        await db.record_tip(tipper_id, recipient_id, guild_id, note)
        await db.increment_tips_given(tipper_id, guild_id, today)

        if abs(new - old) >= DM_NOTIFY_THRESHOLD and await db.get_dm_notify(recipient_id):
            try:
                await user.send(
                    f"**Behaviour Score Update**\n"
                    f"You received a tip from **{interaction.user.display_name}**!\n"
                    f"{old:,} → **{new:,}** / 12,000"
                )
            except discord.Forbidden:
                pass

        tips_remaining = tip_limit - tracking["tips_given"] - 1
        msg = f"👍 Tipped **{user.display_name}**! Their score is now **{new:,} / 12,000**.\n> {note}\n{interaction.user.display_name} has **{tips_remaining}** tip(s) remaining today."
        await interaction.response.send_message(msg)

        tier = check_tier_change(old, new)
        if tier:
            old_label, new_label = tier
            await interaction.channel.send(f"📈 **{user.display_name}** has risen to **{new_label}**!")

        if user.voice and user.voice.channel:
            asyncio.create_task(play_voice_announcement(interaction.guild, user.voice.channel, f"Tip for {user.display_name}. {note}", sound_path=TIP_SOUND_PATH))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tipping(bot))
