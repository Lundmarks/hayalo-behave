import aiosqlite
from config import DATABASE_PATH, SCORE_START, SCORE_MIN, SCORE_MAX

_db: aiosqlite.Connection | None = None

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    user_id   INTEGER NOT NULL,
    guild_id  INTEGER NOT NULL,
    score     INTEGER NOT NULL DEFAULT 10000,
    dm_notify INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS score_events (
    event_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL,
    guild_id  INTEGER NOT NULL,
    delta     INTEGER NOT NULL,
    reason    TEXT    NOT NULL,
    source    TEXT    NOT NULL,
    timestamp TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reports (
    report_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    target_id   INTEGER NOT NULL,
    guild_id    INTEGER NOT NULL,
    reason      TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
    confirmed   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tips (
    tip_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tipper_id    INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    guild_id     INTEGER NOT NULL,
    note         TEXT,
    timestamp    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_tracking (
    user_id                   INTEGER NOT NULL,
    guild_id                  INTEGER NOT NULL,
    date                      TEXT    NOT NULL,
    tips_given                INTEGER NOT NULL DEFAULT 0,
    first_message_bonus_given INTEGER NOT NULL DEFAULT 0,
    passive_earned_today      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, guild_id, date)
);

CREATE TABLE IF NOT EXISTS reaction_tracking (
    reactor_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    timestamp  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (reactor_id, message_id)
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id          INTEGER PRIMARY KEY,
    report_channel_id INTEGER,
    digest_channel_id INTEGER,
    bot_channel_id    INTEGER
);
"""


async def init_db() -> None:
    global _db
    import os
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    _db = await aiosqlite.connect(DATABASE_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(_SCHEMA)
    await _db.commit()


def get_db() -> aiosqlite.Connection:
    return _db


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

async def get_or_create_user(user_id: int, guild_id: int) -> dict:
    conn = get_db()
    async with conn.execute(
        "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        await conn.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id, score) VALUES (?, ?, ?)",
            (user_id, guild_id, SCORE_START),
        )
        await conn.commit()
        async with conn.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        ) as cur:
            row = await cur.fetchone()
    return dict(row)


async def get_user(user_id: int, guild_id: int) -> dict | None:
    conn = get_db()
    async with conn.execute(
        "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_dm_notify(user_id: int) -> bool:
    """Global DM preference — checked across any guild record for this user."""
    conn = get_db()
    async with conn.execute(
        "SELECT dm_notify FROM users WHERE user_id = ? LIMIT 1", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    return bool(row[0]) if row else True


async def set_dm_notify(user_id: int, enabled: bool) -> None:
    """Update DM preference across all guild records for this user."""
    conn = get_db()
    await conn.execute(
        "UPDATE users SET dm_notify = ? WHERE user_id = ?",
        (1 if enabled else 0, user_id),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

async def apply_score_delta(
    user_id: int, guild_id: int, delta: int, reason: str, source: str
) -> tuple[int, int]:
    """Apply a score change. Returns (old_score, new_score)."""
    conn = get_db()
    user = await get_or_create_user(user_id, guild_id)
    old_score = user["score"]
    new_score = max(SCORE_MIN, min(SCORE_MAX, old_score + delta))
    actual_delta = new_score - old_score

    if actual_delta == 0:
        return old_score, old_score

    await conn.execute(
        "UPDATE users SET score = ? WHERE user_id = ? AND guild_id = ?",
        (new_score, user_id, guild_id),
    )
    await conn.execute(
        "INSERT INTO score_events (user_id, guild_id, delta, reason, source) VALUES (?, ?, ?, ?, ?)",
        (user_id, guild_id, actual_delta, reason, source),
    )
    await conn.commit()
    return old_score, new_score


async def get_score_events(user_id: int, guild_id: int, limit: int = 10) -> list[dict]:
    conn = get_db()
    async with conn.execute(
        """SELECT * FROM score_events WHERE user_id = ? AND guild_id = ?
           ORDER BY timestamp DESC LIMIT ?""",
        (user_id, guild_id, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_recent_events(guild_id: int, limit: int = 20) -> list[dict]:
    conn = get_db()
    async with conn.execute(
        "SELECT * FROM score_events WHERE guild_id = ? ORDER BY timestamp DESC LIMIT ?",
        (guild_id, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_rank(user_id: int, guild_id: int) -> int:
    conn = get_db()
    async with conn.execute(
        """SELECT COUNT(*) FROM users
           WHERE guild_id = ? AND score > (
               SELECT score FROM users WHERE user_id = ? AND guild_id = ?
           )""",
        (guild_id, user_id, guild_id),
    ) as cur:
        row = await cur.fetchone()
    return (row[0] + 1) if row else 1


async def get_member_count(guild_id: int) -> int:
    conn = get_db()
    async with conn.execute(
        "SELECT COUNT(*) FROM users WHERE guild_id = ?", (guild_id,)
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else 0


async def get_leaderboard(guild_id: int, limit: int = 10) -> list[dict]:
    conn = get_db()
    async with conn.execute(
        "SELECT user_id, score FROM users WHERE guild_id = ? ORDER BY score DESC LIMIT ?",
        (guild_id, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_server_stats(guild_id: int) -> dict:
    conn = get_db()
    async with conn.execute(
        """SELECT COUNT(*) as count, AVG(score) as avg, MAX(score) as max
           FROM users WHERE guild_id = ?""",
        (guild_id,),
    ) as cur:
        row = await cur.fetchone()
    return {"count": row["count"], "avg": row["avg"] or 0.0, "max": row["max"] or 0}


async def get_tier_breakdown(guild_id: int) -> list[tuple]:
    from config import TIERS
    conn = get_db()
    async with conn.execute(
        "SELECT score FROM users WHERE guild_id = ?", (guild_id,)
    ) as cur:
        scores = [r[0] for r in await cur.fetchall()]
    total = len(scores)
    result = []
    for i, (low, high, label, _) in enumerate(TIERS, 1):
        count = sum(1 for s in scores if low <= s <= high)
        pct = (count / total * 100) if total else 0.0
        result.append((i, label, count, pct))
    return result


# ---------------------------------------------------------------------------
# Daily tracking helpers
# ---------------------------------------------------------------------------

async def get_today_tracking(user_id: int, guild_id: int, date_str: str) -> dict:
    conn = get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO daily_tracking (user_id, guild_id, date) VALUES (?, ?, ?)",
        (user_id, guild_id, date_str),
    )
    await conn.commit()
    async with conn.execute(
        "SELECT * FROM daily_tracking WHERE user_id = ? AND guild_id = ? AND date = ?",
        (user_id, guild_id, date_str),
    ) as cur:
        return dict(await cur.fetchone())


async def try_mark_first_message_bonus(user_id: int, guild_id: int, date_str: str) -> bool:
    """Atomically claim the first-message bonus. Returns True if this call claimed it."""
    conn = get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO daily_tracking (user_id, guild_id, date) VALUES (?, ?, ?)",
        (user_id, guild_id, date_str),
    )
    cur = await conn.execute(
        """UPDATE daily_tracking SET first_message_bonus_given = 1
           WHERE user_id = ? AND guild_id = ? AND date = ? AND first_message_bonus_given = 0""",
        (user_id, guild_id, date_str),
    )
    await conn.commit()
    return cur.rowcount > 0


async def increment_tips_given(user_id: int, guild_id: int, date_str: str) -> None:
    conn = get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO daily_tracking (user_id, guild_id, date) VALUES (?, ?, ?)",
        (user_id, guild_id, date_str),
    )
    await conn.execute(
        """UPDATE daily_tracking SET tips_given = tips_given + 1
           WHERE user_id = ? AND guild_id = ? AND date = ?""",
        (user_id, guild_id, date_str),
    )
    await conn.commit()


async def increment_passive_earned(user_id: int, guild_id: int, date_str: str, amount: int) -> None:
    conn = get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO daily_tracking (user_id, guild_id, date) VALUES (?, ?, ?)",
        (user_id, guild_id, date_str),
    )
    await conn.execute(
        """UPDATE daily_tracking SET passive_earned_today = passive_earned_today + ?
           WHERE user_id = ? AND guild_id = ? AND date = ?""",
        (amount, user_id, guild_id, date_str),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Reaction helpers
# ---------------------------------------------------------------------------

async def check_and_record_reaction(reactor_id: int, message_id: int) -> bool:
    """Try to record a reaction. Returns True if already recorded (skip bonus)."""
    conn = get_db()
    try:
        await conn.execute(
            "INSERT INTO reaction_tracking (reactor_id, message_id) VALUES (?, ?)",
            (reactor_id, message_id),
        )
        await conn.commit()
        return False
    except aiosqlite.IntegrityError:
        return True


# ---------------------------------------------------------------------------
# Tip helpers
# ---------------------------------------------------------------------------

async def record_tip(tipper_id: int, recipient_id: int, guild_id: int, note: str | None) -> None:
    conn = get_db()
    await conn.execute(
        "INSERT INTO tips (tipper_id, recipient_id, guild_id, note) VALUES (?, ?, ?, ?)",
        (tipper_id, recipient_id, guild_id, note),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

async def has_reported_in_24h(reporter_id: int, target_id: int, guild_id: int) -> bool:
    conn = get_db()
    async with conn.execute(
        """SELECT 1 FROM reports
           WHERE reporter_id = ? AND target_id = ? AND guild_id = ?
           AND datetime(timestamp) > datetime('now', '-24 hours')""",
        (reporter_id, target_id, guild_id),
    ) as cur:
        return await cur.fetchone() is not None


async def record_report(reporter_id: int, target_id: int, guild_id: int, reason: str) -> None:
    conn = get_db()
    await conn.execute(
        "INSERT INTO reports (reporter_id, target_id, guild_id, reason) VALUES (?, ?, ?, ?)",
        (reporter_id, target_id, guild_id, reason),
    )
    await conn.commit()


async def get_pending_reports(guild_id: int) -> list[dict]:
    conn = get_db()
    async with conn.execute(
        """SELECT * FROM reports WHERE guild_id = ?
           AND datetime(timestamp) > datetime('now', '-24 hours')
           ORDER BY timestamp DESC""",
        (guild_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


# ---------------------------------------------------------------------------
# Guild config helpers
# ---------------------------------------------------------------------------

async def get_guild_config(guild_id: int) -> dict | None:
    conn = get_db()
    async with conn.execute(
        "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def upsert_guild_config(
    guild_id: int,
    report_channel_id: int | None,
    digest_channel_id: int | None,
    bot_channel_id: int | None,
) -> None:
    conn = get_db()
    await conn.execute(
        """INSERT INTO guild_config (guild_id, report_channel_id, digest_channel_id, bot_channel_id)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET
               report_channel_id = excluded.report_channel_id,
               digest_channel_id = excluded.digest_channel_id,
               bot_channel_id    = excluded.bot_channel_id""",
        (guild_id, report_channel_id, digest_channel_id, bot_channel_id),
    )
    await conn.commit()


async def get_all_guild_configs() -> list[dict]:
    conn = get_db()
    async with conn.execute("SELECT * FROM guild_config") as cur:
        return [dict(r) for r in await cur.fetchall()]


# ---------------------------------------------------------------------------
# Weekly digest helpers
# ---------------------------------------------------------------------------

async def get_top_tipped_this_week(guild_id: int, limit: int = 3) -> list[dict]:
    conn = get_db()
    async with conn.execute(
        """SELECT recipient_id AS user_id, COUNT(*) AS tips_received
           FROM tips
           WHERE guild_id = ? AND datetime(timestamp) > datetime('now', '-7 days')
           GROUP BY recipient_id
           ORDER BY tips_received DESC
           LIMIT ?""",
        (guild_id, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_biggest_mover_this_week(guild_id: int, positive: bool = True) -> dict | None:
    conn = get_db()
    condition = "delta > 0" if positive else "delta < 0"
    order = "total DESC" if positive else "total ASC"
    async with conn.execute(
        f"""SELECT user_id, SUM(delta) AS total
            FROM score_events
            WHERE guild_id = ? AND {condition}
            AND datetime(timestamp) > datetime('now', '-7 days')
            GROUP BY user_id
            ORDER BY {order}
            LIMIT 1""",
        (guild_id,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None
