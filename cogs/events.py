import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

import db.database as db
import utils.state as state
from config import (
    GAIN_FIRST_MESSAGE,
    GAIN_REACTION,
    GAIN_REACTION_WEIGHTED,
    GAIN_REPLY,
    LOSS_SPAM,
    LOSS_BARE_QUESTION,
    LOSS_SWEAR,
    SPAM_MESSAGE_LIMIT,
    SPAM_TIME_WINDOW,
    SWEAR_COOLDOWN,
    SWEAR_WORDS,
    DM_NOTIFY_THRESHOLD,
    TIMEZONE,
)

_SWEAR_SPLIT = re.compile(r"[\s\W]+")


def _contains_swear(text: str) -> bool:
    return any(t in SWEAR_WORDS for t in _SWEAR_SPLIT.split(text.lower()) if t)

TZ = ZoneInfo(TIMEZONE)


async def _maybe_dm(member: discord.Member, old: int, new: int, reason: str | None = None) -> None:
    if abs(new - old) < DM_NOTIFY_THRESHOLD:
        return
    if not await db.get_dm_notify(member.id):
        return
    delta = new - old
    direction = "increased" if delta > 0 else "decreased"
    body = f"Your behaviour score has **{direction}** by {abs(delta):,} points.\n{old:,} → **{new:,}** / 12,000"
    if reason:
        body = f"_{reason}_\n\n" + body
    try:
        await member.send(f"**Behaviour Score Update**\n{body}")
    except discord.Forbidden:
        pass


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        await db.get_or_create_user(member.id, member.guild.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        today = datetime.now(TZ).strftime("%Y-%m-%d")

        await db.get_or_create_user(user_id, guild_id)
        state.active_this_hour.add((user_id, guild_id))

        # First message of the day bonus
        claimed = await db.try_mark_first_message_bonus(user_id, guild_id, today)
        if claimed:
            old, new = await db.apply_score_delta(
                user_id, guild_id, GAIN_FIRST_MESSAGE, "First message of the day", "passive"
            )
            await _maybe_dm(message.author, old, new)

        # Reply bonus
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            original = message.reference.resolved
            if not original.author.bot and original.author.id != user_id:
                await db.get_or_create_user(original.author.id, guild_id)
                old, new = await db.apply_score_delta(
                    original.author.id, guild_id, GAIN_REPLY,
                    f"Received a reply from {message.author.display_name}", "reply",
                )
                orig_member = message.guild.get_member(original.author.id)
                if orig_member:
                    await _maybe_dm(orig_member, old, new)

        # Spam detection — sliding window
        now = time.monotonic()
        ts = state.message_timestamps[user_id]
        ts.append(now)
        cutoff = now - SPAM_TIME_WINDOW
        while ts and ts[0] < cutoff:
            ts.popleft()

        if len(ts) > SPAM_MESSAGE_LIMIT:
            last_penalty = state.spam_cooldowns.get(user_id, 0.0)
            if now - last_penalty > 300:
                state.spam_cooldowns[user_id] = now
                old, new = await db.apply_score_delta(
                    user_id, guild_id, -LOSS_SPAM, "Spam detection", "spam"
                )
                await _maybe_dm(message.author, old, new, "You were penalised for spamming.")

        # Bare question mark
        if message.content.strip() == "?":
            old, new = await db.apply_score_delta(
                user_id, guild_id, -LOSS_BARE_QUESTION, "Bare question mark", "message_content"
            )
            await _maybe_dm(message.author, old, new)

        # Swearing
        if _contains_swear(message.content):
            last_swear = state.swear_cooldowns.get(user_id, 0.0)
            if now - last_swear > SWEAR_COOLDOWN:
                state.swear_cooldowns[user_id] = now
                old, new = await db.apply_score_delta(
                    user_id, guild_id, -LOSS_SWEAR, "Swearing", "message_content"
                )
                await _maybe_dm(message.author, old, new)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if not payload.guild_id:
            return
        if payload.member and payload.member.bot:
            return

        reactor_id = payload.user_id
        message_id = payload.message_id

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        author = message.author
        if author.bot or author.id == reactor_id:
            return

        already_recorded = await db.check_and_record_reaction(reactor_id, message_id)
        if already_recorded:
            return

        await db.get_or_create_user(author.id, payload.guild_id)
        reactor_name = payload.member.display_name if payload.member else "a user"
        gain = GAIN_REACTION_WEIGHTED.get(str(payload.emoji), GAIN_REACTION)
        old, new = await db.apply_score_delta(
            author.id, payload.guild_id, gain,
            f"Received a {payload.emoji} reaction from {reactor_name}", "reaction",
        )
        author_member = message.guild.get_member(author.id) if message.guild else None
        if author_member:
            await _maybe_dm(author_member, old, new)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
