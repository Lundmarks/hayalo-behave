from config import TIERS, SCORE_MAX, SCORE_MIN
import discord


def get_tier(score: int) -> tuple[int, str, int]:
    """Returns (tier_number, label, daily_tip_limit)."""
    for i, (low, high, label, tip_limit) in enumerate(TIERS, 1):
        if low <= score <= high:
            return i, label, tip_limit
    # Fallback for scores exactly at boundaries
    if score >= TIERS[-1][0]:
        t = TIERS[-1]
        return len(TIERS), t[2], t[3]
    t = TIERS[0]
    return 1, t[2], t[3]


def format_score_bar(score: int, width: int = 20) -> str:
    filled = round((score / SCORE_MAX) * width)
    return f"`[{'█' * filled}{'░' * (width - filled)}]`"


def tier_color(tier_num: int) -> discord.Color:
    return {
        1: discord.Color.red(),
        2: discord.Color.orange(),
        3: discord.Color.yellow(),
        4: discord.Color.green(),
        5: discord.Color.gold(),
    }.get(tier_num, discord.Color.default())
