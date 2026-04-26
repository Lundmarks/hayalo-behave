import discord
from discord import app_commands
from discord.ext import commands

import db.database as db
from config import SCORE_MAX
from utils.score_utils import get_tier, format_score_bar, tier_color


class Score(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="score", description="View your or another user's behaviour score")
    @app_commands.describe(user="The user to look up (leave empty for yourself)")
    async def score(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        target = user or interaction.user
        guild_id = interaction.guild_id
        data = await db.get_or_create_user(target.id, guild_id)
        score_val = data["score"]
        tier_num, tier_label, _ = get_tier(score_val)
        rank = await db.get_rank(target.id, guild_id)
        total = await db.get_member_count(guild_id)

        embed = discord.Embed(
            title=f"Behaviour Score — {target.display_name}",
            color=tier_color(tier_num),
        )
        embed.add_field(name="Score", value=f"**{score_val:,}** / {SCORE_MAX:,}", inline=True)
        embed.add_field(name="Tier", value=tier_label, inline=True)
        embed.add_field(name="Rank", value=f"#{rank} of {total}", inline=True)
        embed.add_field(name="Progress", value=format_score_bar(score_val), inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Top 10 behaviour scores in the server")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await db.get_leaderboard(interaction.guild_id)
        embed = discord.Embed(title="Behaviour Score Leaderboard", color=discord.Color.gold())
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for i, row in enumerate(rows, 1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"Unknown ({row['user_id']})"
            _, tier_label, _ = get_tier(row["score"])
            prefix = medals.get(i, f"**{i}.**")
            lines.append(f"{prefix} {name} — {row['score']:,} ({tier_label})")
        embed.description = "\n".join(lines) if lines else "No scores recorded yet."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="history", description="View score change history for any user")
    @app_commands.describe(user="The user to inspect (leave empty for yourself)")
    async def history(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ) -> None:
        target = user or interaction.user
        events = await db.get_score_events(target.id, interaction.guild_id, limit=10)

        embed = discord.Embed(
            title=f"Score History — {target.display_name}",
            color=discord.Color.blurple(),
        )
        if not events:
            embed.description = "No score events recorded yet."
        else:
            lines = []
            for e in events:
                delta = e["delta"]
                sign = "+" if delta >= 0 else ""
                ts = e["timestamp"][:10]
                lines.append(f"`{ts}` **{sign}{delta}** — {e['reason']}")
            embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server-stats", description="Server-wide behaviour score statistics")
    async def server_stats(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        stats = await db.get_server_stats(guild_id)
        breakdown = await db.get_tier_breakdown(guild_id)

        embed = discord.Embed(title="Server Behaviour Stats", color=discord.Color.teal())
        embed.add_field(name="Tracked Members", value=str(stats["count"]), inline=True)
        embed.add_field(name="Average Score", value=f"{stats['avg']:.0f} / {SCORE_MAX:,}", inline=True)
        embed.add_field(name="Top Score", value=f"{stats['max']:,}", inline=True)
        breakdown_lines = [f"{label}: {count} ({pct:.1f}%)" for _, label, count, pct in breakdown]
        embed.add_field(
            name="Tier Breakdown",
            value="\n".join(breakdown_lines) if breakdown_lines else "—",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="notifications", description="Toggle DM notifications for score changes")
    async def notifications(self, interaction: discord.Interaction) -> None:
        await db.get_or_create_user(interaction.user.id, interaction.guild_id)
        current = await db.get_dm_notify(interaction.user.id)
        await db.set_dm_notify(interaction.user.id, not current)
        status = "disabled" if current else "enabled"
        await interaction.response.send_message(
            f"DM notifications **{status}**.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Score(bot))
