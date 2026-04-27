import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from config import TOKEN, LOSS_BOT_CHANNEL, BOT_CHANNEL_EXEMPT
import db.database as db
from utils.scheduler import setup_scheduler

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True


class BehaviourCommandTree(app_commands.CommandTree):
    """Intercepts every slash command to enforce the bot-commands channel restriction."""

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if not interaction.guild_id:
            return True

        command = interaction.command
        if command is None or command.name in BOT_CHANNEL_EXEMPT:
            return True

        config = await db.get_guild_config(interaction.guild_id)
        if not config:
            return True

        bot_channel_id = config.get("bot_channel_id")
        if not bot_channel_id or interaction.channel_id == bot_channel_id:
            return True

        # Wrong channel — deduct score and block
        await db.get_or_create_user(interaction.user.id, interaction.guild_id)
        await db.apply_score_delta(
            interaction.user.id,
            interaction.guild_id,
            -LOSS_BOT_CHANNEL,
            f"Used bot commands outside <#{bot_channel_id}>",
            "bot_channel",
        )
        ch = interaction.guild.get_channel(bot_channel_id) if interaction.guild else None
        mention = ch.mention if ch else "the designated bot channel"
        await interaction.response.send_message(
            f"Please use bot commands in {mention}. (−{LOSS_BOT_CHANNEL} behaviour score)",
            ephemeral=True,
        )
        return False


class BehaveBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents, tree_cls=BehaviourCommandTree)
        self.scheduler = None

    async def setup_hook(self) -> None:
        await db.init_db()

        for cog in (
            "cogs.events",
            "cogs.tipping",
            "cogs.reports",
            "cogs.score",
            "cogs.moderation",
            "cogs.setup",
        ):
            await self.load_extension(cog)

        self.scheduler = setup_scheduler(self)
        self.scheduler.start()

    async def on_ready(self) -> None:
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        guild_names = ", ".join(g.name for g in self.guilds) or "none"
        print(f"Ready — {self.user} | guilds: {guild_names}")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Sync commands instantly whenever the bot joins a new server."""
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"Joined guild: {guild.name} ({guild.id})")

    async def close(self) -> None:
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await db.close_db()
        await super().close()


bot = BehaveBot()

if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
