import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

import discord
from discord import app_commands
from discord.ext import commands

import db.database as db
from config import (
    SCORE_MAX, SCORE_MIN, SCORE_START,
    GAIN_TIP, GAIN_FIRST_MESSAGE, GAIN_PASSIVE_HOURLY, GAIN_PASSIVE_DAILY_CAP,
    GAIN_REACTION, GAIN_REPLY,
    LOSS_REPORT, LOSS_SPAM, LOSS_SPAM_REPORT, LOSS_BOT_CHANNEL,
    LOSS_BARE_QUESTION, LOSS_SWEAR,
    TIERS,
)
from utils.score_utils import get_tier, format_score_bar, tier_color

_CHART_BG = "#2b2d31"
_CHART_AX = "#1e1f22"
_CHART_LINE = "#5865f2"
_CHART_TEXT = "#dbdee1"
_CHART_GRID = "#3f4147"
_TIER_COLORS = ["#ed4245", "#f57f17", "#fee75c", "#57f287", "#ffd700"]


def _build_history_chart(display_name: str, current_score: int, events: list[dict]) -> io.BytesIO:
    events_asc = list(reversed(events))
    base = current_score - sum(e["delta"] for e in events_asc)

    scores = [base]
    for e in events_asc:
        scores.append(scores[-1] + e["delta"])

    dates = [""] + [e["timestamp"][:10] for e in events_asc]

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor(_CHART_BG)
    ax.set_facecolor(_CHART_AX)

    xs = list(range(len(scores)))
    ax.plot(xs, scores, color=_CHART_LINE, linewidth=2, marker="o", markersize=4, zorder=3)
    ax.fill_between(xs, scores, alpha=0.12, color=_CHART_LINE)

    for (low, _, _, _), color in zip(TIERS, _TIER_COLORS):
        if low > 0:
            ax.axhline(y=low, color=color, linewidth=0.6, alpha=0.35, linestyle="--", zorder=1)

    score_range = max(scores) - min(scores)
    pad = max(300, score_range * 0.15)
    ax.set_ylim(max(0, min(scores) - pad), min(SCORE_MAX + 200, max(scores) + pad))
    ax.set_xlim(-0.3, len(scores) - 0.7)

    step = max(1, len(dates) // 7)
    tick_xs = list(range(0, len(dates), step))
    ax.set_xticks(tick_xs)
    ax.set_xticklabels([dates[i] for i in tick_xs], rotation=30, ha="right", fontsize=7, color=_CHART_TEXT)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.tick_params(axis="y", colors=_CHART_TEXT, labelsize=8)
    ax.yaxis.tick_right()

    for spine in ax.spines.values():
        spine.set_edgecolor(_CHART_GRID)
    ax.grid(axis="y", color=_CHART_GRID, linewidth=0.5, alpha=0.5)
    ax.set_title(f"Score History — {display_name}", color=_CHART_TEXT, fontsize=11, pad=10)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=_CHART_BG)
    plt.close(fig)
    buf.seek(0)
    return buf


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
        await interaction.response.defer()

        data = await db.get_or_create_user(target.id, interaction.guild_id)
        events = await db.get_score_events(target.id, interaction.guild_id, limit=20)

        if not events:
            await interaction.followup.send(f"No score history recorded yet for **{target.display_name}**.")
            return

        buf = _build_history_chart(target.display_name, data["score"], events)
        file = discord.File(buf, filename="history.png")
        await interaction.followup.send(file=file)

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

    @app_commands.command(name="rules", description="How the behaviour score system works")
    async def rules(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Behaviour Score — How It Works",
            description=(
                f"Every member starts at **{SCORE_START:,}** points. "
                f"Score is capped between **{SCORE_MIN}** and **{SCORE_MAX:,}**."
            ),
            color=discord.Color.blurple(),
        )

        tier_lines = "\n".join(
            f"`{low:,}–{high:,}` {label} — {tips} tip(s)/day"
            for low, high, label, tips in TIERS
        )
        embed.add_field(name="Tiers", value=tier_lines, inline=False)

        gains = (
            f"+{GAIN_TIP} — Receiving a tip\n"
            f"+{GAIN_REPLY} — Someone replies to your message\n"
            f"+{GAIN_REACTION} — Someone reacts to your message\n"
            f"+{GAIN_FIRST_MESSAGE} — First message of the day\n"
            f"+{GAIN_PASSIVE_HOURLY}/hr — Active in the last hour (max +{GAIN_PASSIVE_DAILY_CAP}/day)"
        )
        embed.add_field(name="Ways to Earn", value=gains, inline=False)

        losses = (
            f"−{LOSS_REPORT} — Being reported\n"
            f"−{LOSS_SPAM} — Sending messages too fast\n"
            f"−{LOSS_SWEAR} — Swearing\n"
            f"−{LOSS_BARE_QUESTION} — Sending only `?`\n"
            f"−{LOSS_BOT_CHANNEL} — Using bot commands outside the designated channel\n"
            f"−{LOSS_SPAM_REPORT} — Reporting the same person twice within 24 hours"
        )
        embed.add_field(name="Ways to Lose", value=losses, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="notifications", description="Toggle DM notifications for score changes")
    async def notifications(self, interaction: discord.Interaction) -> None:
        await db.get_or_create_user(interaction.user.id, interaction.guild_id)
        current = await db.get_dm_notify(interaction.user.id)
        await db.set_dm_notify(interaction.user.id, not current)
        status = "disabled" if current else "enabled"
        await interaction.response.send_message(
            f"DM notifications **{status}**."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Score(bot))
