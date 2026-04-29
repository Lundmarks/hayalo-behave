import discord
from discord import app_commands
from discord.ext import commands

import db.database as db
from utils.score_utils import check_tier_change


def _is_mod(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.manage_guild  # type: ignore[union-attr]


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="mod-log", description="[MOD] View the 20 most recent score change events")
    async def mod_log(self, interaction: discord.Interaction) -> None:
        if not _is_mod(interaction):
            await interaction.response.send_message("You need Manage Server permission.", ephemeral=False)
            return

        events = await db.get_recent_events(interaction.guild_id, limit=20)
        embed = discord.Embed(title="Recent Score Events", color=discord.Color.dark_gray())

        if not events:
            embed.description = "No events recorded yet."
        else:
            lines = []
            for e in events:
                member = interaction.guild.get_member(e["user_id"])
                name = member.display_name if member else f"User {e['user_id']}"
                delta = e["delta"]
                sign = "+" if delta >= 0 else ""
                ts = e["timestamp"][:16]
                lines.append(f"`{ts}` **{name}** {sign}{delta} [{e['source']}] — {e['reason'][:60]}")
            embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="mod-adjust", description="[MOD] Manually adjust a user's behaviour score")
    @app_commands.describe(
        user="The user to adjust",
        amount="Points to add (positive) or remove (negative)",
        reason="Reason for the adjustment (logged and shown in history)",
    )
    async def mod_adjust(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
        reason: str,
    ) -> None:
        if not _is_mod(interaction):
            await interaction.response.send_message("You need Manage Server permission.", ephemeral=False)
            return

        await db.get_or_create_user(user.id, interaction.guild_id)
        old, new = await db.apply_score_delta(
            user.id, interaction.guild_id, amount,
            f"[MOD] {reason} (by {interaction.user.display_name})", "mod",
        )

        sign = "+" if amount >= 0 else ""
        tier = check_tier_change(old, new)
        tier_line = ""
        if tier:
            old_label, new_label = tier
            direction = "risen to" if new > old else "fallen to"
            emoji = "📈" if new > old else "📉"
            tier_line = f"\n{emoji} **{user.display_name}** has {direction} **{new_label}**."
        await interaction.response.send_message(
            f"Adjusted **{user.display_name}**: {old:,} → **{new:,}** ({sign}{amount})\nReason: {reason}{tier_line}",
            ephemeral=False,
        )

    @app_commands.command(name="mod-pending-reports", description="[MOD] List all unconfirmed reports in the last 24 hours")
    async def mod_pending_reports(self, interaction: discord.Interaction) -> None:
        if not _is_mod(interaction):
            await interaction.response.send_message("You need Manage Server permission.", ephemeral=False)
            return

        reports = await db.get_pending_reports(interaction.guild_id)
        embed = discord.Embed(title="Pending Reports (last 24 h)", color=discord.Color.orange())

        if not reports:
            embed.description = "No pending reports."
        else:
            lines = []
            for r in reports:
                target = interaction.guild.get_member(r["target_id"])
                target_name = target.display_name if target else f"User {r['target_id']}"
                lines.append(f"`{r['timestamp'][:10]}` **{target_name}** — {r['reason'][:80]}")
            embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
