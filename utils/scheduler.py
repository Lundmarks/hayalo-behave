from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db.database as db
import utils.state as state
from config import GAIN_PASSIVE_HOURLY, GAIN_PASSIVE_DAILY_CAP, TIMEZONE

TZ = ZoneInfo(TIMEZONE)


def setup_scheduler(bot: discord.Client) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        _passive_recovery,
        CronTrigger(minute=0, timezone=TIMEZONE),
        args=[bot],
        id="passive_recovery",
        replace_existing=True,
    )
    scheduler.add_job(
        _weekly_digest,
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=TIMEZONE),
        args=[bot],
        id="weekly_digest",
        replace_existing=True,
    )

    return scheduler


async def _passive_recovery(bot: discord.Client) -> None:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    for user_id, guild_id in list(state.active_this_hour):
        try:
            tracking = await db.get_today_tracking(user_id, guild_id, today)
            already = tracking["passive_earned_today"]
            if already >= GAIN_PASSIVE_DAILY_CAP:
                continue
            amount = min(GAIN_PASSIVE_HOURLY, GAIN_PASSIVE_DAILY_CAP - already)
            await db.apply_score_delta(user_id, guild_id, amount, "Passive hourly recovery", "passive")
            await db.increment_passive_earned(user_id, guild_id, today, amount)
        except Exception:
            pass
    state.active_this_hour.clear()


async def _weekly_digest(bot: discord.Client) -> None:
    configs = await db.get_all_guild_configs()
    for config in configs:
        guild_id = config["guild_id"]
        digest_channel_id = config.get("digest_channel_id")
        if not digest_channel_id:
            continue
        guild = bot.get_guild(guild_id)
        if not guild:
            continue
        channel = guild.get_channel(digest_channel_id)
        if not channel:
            continue

        stats = await db.get_server_stats(guild_id)
        breakdown = await db.get_tier_breakdown(guild_id)
        top_tipped = await db.get_top_tipped_this_week(guild_id, limit=3)
        biggest_gain = await db.get_biggest_mover_this_week(guild_id, positive=True)
        biggest_loss = await db.get_biggest_mover_this_week(guild_id, positive=False)

        lines = [
            "## 📊 Weekly Behaviour Digest",
            "",
            f"**Server average score:** {stats['avg']:.0f} / 12,000",
            f"**Tracked members:** {stats['count']}",
            "",
            "**Tier breakdown:**",
        ]
        for _, label, count, pct in breakdown:
            lines.append(f"  {label}: {count} ({pct:.1f}%)")

        if top_tipped:
            lines.append("")
            lines.append("**🏆 Most tipped this week:**")
            for i, row in enumerate(top_tipped, 1):
                member = guild.get_member(row["user_id"])
                name = member.display_name if member else f"User {row['user_id']}"
                lines.append(f"  {i}. {name} — {row['tips_received']} tips")

        if biggest_gain:
            member = guild.get_member(biggest_gain["user_id"])
            name = member.display_name if member else f"User {biggest_gain['user_id']}"
            lines.append(f"\n**📈 Biggest gain:** {name} (+{biggest_gain['total']:,})")

        if biggest_loss:
            member = guild.get_member(biggest_loss["user_id"])
            name = member.display_name if member else f"User {biggest_loss['user_id']}"
            lines.append(f"**📉 Biggest loss:** {name} ({biggest_loss['total']:,})")

        try:
            await channel.send("\n".join(lines))
        except discord.Forbidden:
            pass
