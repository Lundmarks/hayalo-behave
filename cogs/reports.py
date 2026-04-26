import random

import discord
from discord import app_commands
from discord.ext import commands

import db.database as db

_REPORT_QUIPS = [
    "⚖️ *The council has spoken.*",
    "📉 *Another one bites the dust.*",
    "🫵 *Someone saw what you did.*",
    "🧂 *Salty behaviour detected.*",
    "🏚️ *Low priority queue incoming.*",
    "😬 *Yikes.*",
    "🎭 *The community remembers.*",
    "🪦 *RIP behaviour score.*",
    "🤝 *This could have been avoided.*",
    "🔔 *Ding ding ding — we have a problem.*",
]
from config import LOSS_REPORT, LOSS_SPAM_REPORT


class Reports(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="report", description="Anonymously report a user for misconduct")
    @app_commands.describe(
        user="The user to report",
        reason="Reason for the report (max 200 characters)",
    )
    async def report(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
    ) -> None:
        reporter_id = interaction.user.id
        target_id = user.id
        guild_id = interaction.guild_id
        reason = reason[:200].strip()

        if not reason:
            await interaction.response.send_message("Please provide a reason for the report.", ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message("You cannot report bots.", ephemeral=True)
            return
        if reporter_id == target_id:
            await interaction.response.send_message("You cannot report yourself.", ephemeral=True)
            return

        if await db.has_reported_in_24h(reporter_id, target_id, guild_id):
            await db.get_or_create_user(reporter_id, guild_id)
            await db.apply_score_delta(
                reporter_id, guild_id, -LOSS_SPAM_REPORT,
                f"Spam-reporting {user.display_name}", "spam_report",
            )
            await interaction.response.send_message(
                f"You have already reported this user in the last 24 hours. Repeated reports result in a −{LOSS_SPAM_REPORT} penalty.",
                ephemeral=True,
            )
            return

        await db.get_or_create_user(target_id, guild_id)
        await db.record_report(reporter_id, target_id, guild_id, reason)
        old, new = await db.apply_score_delta(
            target_id, guild_id, -LOSS_REPORT,
            f"Reported: {reason}", "report",
        )

        announcement = (
            f"🚨 **{user.display_name}** has been reported.\n"
            f"**Reason:** {reason}\n"
            f"Score: {old:,} → **{new:,}** / 12,000\n"
            f"{random.choice(_REPORT_QUIPS)}"
        )
        await interaction.channel.send(announcement)

        config = await db.get_guild_config(guild_id)
        report_channel_id = config.get("report_channel_id") if config else None
        if report_channel_id and report_channel_id != interaction.channel_id:
            report_channel = interaction.guild.get_channel(report_channel_id)
            if report_channel:
                await report_channel.send(announcement)

        if await db.get_dm_notify(target_id):
            try:
                await user.send(
                    f"**Behaviour Score Update**\n"
                    f"You have been reported.\n"
                    f"**Reason:** {reason}\n"
                    f"{old:,} → **{new:,}** / 12,000"
                )
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            "Your report has been submitted anonymously. Thank you.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reports(bot))
