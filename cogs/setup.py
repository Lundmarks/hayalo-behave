import os

import discord
from discord import app_commands
from discord.ext import commands

import db.database as db
from config import TIP_SOUND_PATH, SPAM_MESSAGE_LIMIT, SPAM_TIME_WINDOW


def _is_mod(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.manage_guild  # type: ignore[union-attr]


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="setup", description="[MOD] Configure channels for this server (re-run to change)")
    @app_commands.describe(
        report_channel="Channel where anonymous report announcements are posted",
        digest_channel="Channel where the weekly Monday digest is posted",
        bot_channel="Channel where bot commands must be used (leave empty for no restriction)",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        report_channel: discord.TextChannel,
        digest_channel: discord.TextChannel,
        bot_channel: discord.TextChannel | None = None,
    ) -> None:
        if not _is_mod(interaction):
            await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
            return

        await db.upsert_guild_config(
            interaction.guild_id,
            report_channel_id=report_channel.id,
            digest_channel_id=digest_channel.id,
            bot_channel_id=bot_channel.id if bot_channel else None,
        )

        lines = [
            "✅ Configuration saved.",
            f"  Report channel: {report_channel.mention}",
            f"  Digest channel: {digest_channel.mention}",
            f"  Bot commands channel: {bot_channel.mention if bot_channel else 'no restriction'}",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="bot-check", description="[MOD] Verify the bot configuration is correct")
    async def check_config(self, interaction: discord.Interaction) -> None:
        if not _is_mod(interaction):
            await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        lines = ["**Bot Configuration Check**", ""]

        # Database
        try:
            await db.get_guild_config(interaction.guild_id)
            lines.append("✅ Database — responding")
        except Exception as e:
            lines.append(f"❌ Database — {e}")
            await interaction.followup.send("\n".join(lines), ephemeral=True)
            return

        config = await db.get_guild_config(interaction.guild_id)
        if not config:
            lines.append("⚠️  Setup not run yet — use `/setup` to configure channels")
            await interaction.followup.send("\n".join(lines), ephemeral=True)
            return

        me = interaction.guild.me

        # Report channel
        ch_id = config.get("report_channel_id")
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            if ch and ch.permissions_for(me).send_messages:
                lines.append(f"✅ Report channel — {ch.mention}")
            elif ch:
                lines.append(f"❌ Report channel — {ch.mention} (bot lacks Send Messages)")
            else:
                lines.append(f"❌ Report channel — not found (ID {ch_id})")
        else:
            lines.append("❌ Report channel — not configured")

        # Digest channel
        ch_id = config.get("digest_channel_id")
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            if ch and ch.permissions_for(me).send_messages:
                lines.append(f"✅ Digest channel — {ch.mention}")
            elif ch:
                lines.append(f"❌ Digest channel — {ch.mention} (bot lacks Send Messages)")
            else:
                lines.append(f"❌ Digest channel — not found (ID {ch_id})")
        else:
            lines.append("❌ Digest channel — not configured")

        # Bot commands channel
        ch_id = config.get("bot_channel_id")
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            if ch:
                lines.append(f"✅ Bot commands channel — {ch.mention} (restricted, −{50} outside)")
            else:
                lines.append(f"❌ Bot commands channel — not found (ID {ch_id})")
        else:
            lines.append("✅ Bot commands channel — no restriction")

        # Tip sound
        if os.path.isfile(TIP_SOUND_PATH):
            lines.append(f"✅ Tip sound — {TIP_SOUND_PATH}")
        else:
            lines.append(f"⚠️  Tip sound — {TIP_SOUND_PATH} missing (voice tips disabled)")

        # Voice permissions
        voice_ok = any(
            vc.permissions_for(me).connect and vc.permissions_for(me).speak
            for vc in interaction.guild.voice_channels
        )
        if voice_ok:
            lines.append("✅ Voice — Connect & Speak granted in at least one channel")
        else:
            lines.append("⚠️  Voice — no voice channel where bot can Connect & Speak")

        # Spam config
        lines.append(f"✅ Spam detection — {SPAM_MESSAGE_LIMIT} messages / {SPAM_TIME_WINDOW}s window")

        await interaction.followup.send("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))
