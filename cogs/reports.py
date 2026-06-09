import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import config as config_module
import db.database as db
from config import REPORT_SOUND_PATH, TIP_REPORT_CHAR_LIMIT
from utils.voice import play_voice_announcement

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
    "🍕 *Even the staff at Tallboda Europizza are disappointed.*",
    "🍕 *Tallboda Europizza has revoked your loyalty discount.*",
    "🩺 *Dr Carl Johan has reviewed your case and recommends immediate behaviour correction.*",
    "🩺 *Dr Carl Johan sighs deeply and reaches for the clipboard.*",
    "🦁 *Mufasa watches from the great north. He is not impressed.*",
    "🌨️ *Word has reached far northern Sweden. Mufasa shakes his head.*",
    "🚀 *Torpedläge. You are in torpedläge.*",
    "💥 *Full torpedläge detected. Brace for impact.*",
    "⛪ *Emanuelkyrkan will hold a service in your honour. It will be a sad one.*",
    "⛪ *The bells of Emanuelkyrkan toll for thee.*",
    "🎲 *Pangolier would roll right out of this server if he could.*",
    "🎲 *Not even Pangolier's lucky die could save you now.*",
    "🎰 *Pangolier has seen your behaviour and folded his cards.*",
]
from config import LOSS_REPORT, LOSS_SPAM_REPORT
from utils.score_utils import check_tier_change, get_tier


async def _voice_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=name, value=name)
        for name in config_module.ELEVENLABS_VOICE_OPTIONS
        if current.lower() in name.lower()
    ][:25]


class Reports(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="report", description="Anonymously report a user for misconduct")
    @app_commands.describe(
        user="The user to report",
        reason=f"Reason for the report (max {TIP_REPORT_CHAR_LIMIT} characters)",
        voice="Voice to use for the announcement (optional)",
    )
    @app_commands.autocomplete(voice=_voice_autocomplete)
    async def report(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        voice: str = "",
    ) -> None:
        reporter_id = interaction.user.id
        target_id = user.id
        guild_id = interaction.guild_id
        reason = reason.strip()

        if len(reason) > TIP_REPORT_CHAR_LIMIT:
            await interaction.response.send_message(f"Reason cannot exceed {TIP_REPORT_CHAR_LIMIT} characters.", ephemeral=True)
            return
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

        tier = check_tier_change(old, new)
        tier_line = f"\n📉 They have fallen to **{tier[1]}**." if tier else ""
        announcement = (
            f"🚨 **{user.display_name}** has been reported.\n"
            f"**Reason:** {reason}\n"
            f"Score: {old:,} → **{new:,}** / 12,000\n"
            f"{random.choice(_REPORT_QUIPS)}"
            f"{tier_line}"
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

        if user.voice and user.voice.channel:
            voice_id = config_module.ELEVENLABS_VOICE_OPTIONS.get(voice) if voice else None
            asyncio.create_task(
                play_voice_announcement(
                    interaction.guild, user.voice.channel,
                    f"{user.display_name} has been reported. Reason: {reason}",
                    sound_path=REPORT_SOUND_PATH,
                    voice_id=voice_id,
                )
            )

        await interaction.response.send_message(
            "Your report has been submitted anonymously. Thank you.", ephemeral=True
        )


    @app_commands.command(name="report-stats", description="Overview of server report history")
    async def report_stats(self, interaction: discord.Interaction) -> None:
        stats = await db.get_report_stats(interaction.guild_id)

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

        embed = discord.Embed(title="📋 Report Hall of Shame", color=discord.Color.dark_red())
        embed.add_field(
            name="📊 Totals",
            value=f"**{stats['total']:,}** reports all-time\n**{stats['last_7d']:,}** in the last 7 days",
            inline=False,
        )

        if stats["most_reported"]:
            lines = []
            for i, row in enumerate(stats["most_reported"]):
                member = interaction.guild.get_member(row["target_id"])
                name = member.display_name if member else f"User {row['target_id']}"
                user_data = await db.get_user(row["target_id"], interaction.guild_id)
                tier_label = get_tier(user_data["score"])[1] if user_data else "?"
                lines.append(f"{medals[i]} **{name}** — {row['cnt']} reports *(currently {tier_label})*")
            embed.add_field(name="🎯 Most Reported", value="\n".join(lines), inline=False)

        if stats["top_reporters"]:
            lines = []
            for i, row in enumerate(stats["top_reporters"]):
                member = interaction.guild.get_member(row["reporter_id"])
                name = member.display_name if member else f"User {row['reporter_id']}"
                lines.append(f"{medals[i]} **{name}** — {row['cnt']} filed")
            embed.add_field(name="🕵️ Most Active Reporters", value="\n".join(lines), inline=False)

        if stats["total"] == 0:
            embed.description = "*No reports on record. This server is either very well-behaved or very unobserved.*"

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reports(bot))
