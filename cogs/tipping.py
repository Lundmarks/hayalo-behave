import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

import db.database as db
from config import GAIN_TIP, TIMEZONE, DM_NOTIFY_THRESHOLD, TIP_SOUND_PATH
from utils.score_utils import get_tier

TZ = ZoneInfo(TIMEZONE)


async def _play_tip_sound(guild: discord.Guild, voice_channel: discord.VoiceChannel) -> None:
    if not os.path.isfile(TIP_SOUND_PATH):
        return
    if guild.voice_client and guild.voice_client.is_connected():
        return

    vc: discord.VoiceClient | None = None
    try:
        vc = await voice_channel.connect(timeout=10.0, reconnect=False)
        vc.play(discord.FFmpegPCMAudio(TIP_SOUND_PATH))
        while vc.is_playing():
            await asyncio.sleep(0.3)
    except Exception:
        pass
    finally:
        try:
            if vc and vc.is_connected():
                await vc.disconnect(force=True)
        except Exception:
            pass


class Tipping(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="tip", description="Commend a user and raise their behaviour score by 100")
    @app_commands.describe(
        user="The user to commend",
        note="Optional note attached to the tip (shown in their history)",
    )
    async def tip(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        note: str | None = None,
    ) -> None:
        tipper_id = interaction.user.id
        recipient_id = user.id
        guild_id = interaction.guild_id
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        if user.bot:
            await interaction.response.send_message("You cannot tip bots.", ephemeral=True)
            return
        if tipper_id == recipient_id:
            await interaction.response.send_message("You cannot tip yourself.", ephemeral=True)
            return

        tipper = await db.get_or_create_user(tipper_id, guild_id)
        _, _, tip_limit = get_tier(tipper["score"])
        tracking = await db.get_today_tracking(tipper_id, guild_id, today)

        if tracking["tips_given"] >= tip_limit:
            await interaction.response.send_message(
                f"You have used all **{tip_limit}** of your daily tips. They reset at midnight (GMT+2).",
                ephemeral=True,
            )
            return

        await db.get_or_create_user(recipient_id, guild_id)
        reason = f"Tip from {interaction.user.display_name}"
        if note:
            reason += f": {note[:100]}"
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
        await interaction.response.send_message(
            f"Tipped **{user.display_name}**! Their score is now **{new:,} / 12,000**.\n"
            f"You have **{tips_remaining}** tip(s) remaining today.",
            ephemeral=True,
        )

        if user.voice and user.voice.channel:
            asyncio.create_task(_play_tip_sound(interaction.guild, user.voice.channel))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tipping(bot))
