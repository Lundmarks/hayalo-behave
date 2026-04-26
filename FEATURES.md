# Behave Bot — Features & Implementations

## Score System

- Range: **0–12,000**
- New members start at **10,000**
- Score is hard-capped at 12,000 and floored at 0
- Score changes are always logged with a reason and source

## Tiers

| Tier | Range       | Label     | Tips/Day |
|------|-------------|-----------|----------|
| 1    | 0–2,999     | Toxic     | 1        |
| 2    | 3,000–5,999 | Low       | 2        |
| 3    | 6,000–8,999 | Normal    | 3        |
| 4    | 9,000–11,499| Good      | 4        |
| 5    | 11,500–12,000| Pinnacle | 5        |

Tiers are cosmetic and affect tip limits only — they do not restrict server access.

---

## Score Gains

| Source                        | Amount           | Notes                                      |
|-------------------------------|------------------|--------------------------------------------|
| Receiving a tip               | +100             | Per tip received                           |
| First message of the day      | +20              | Once per UTC calendar day                  |
| Passive hourly recovery       | +5               | Per hour with at least 1 message; capped at +50/day |
| Receiving any reaction        | +10              | Per unique user per message (all emoji count)   |
| Receiving a reply             | +30              | Only when someone replies to your message; replying to your own post grants nothing |

---

## Score Losses

| Source                             | Amount | Notes                                           |
|------------------------------------|--------|-------------------------------------------------|
| Confirmed report (2 in 24h)        | −300   | Fixed value; rolling 24h window                 |
| Spam detection                     | −100   | Auto; cooldown of 5 min per user between penalties |
| Manual mod adjustment              | Custom | Via `/mod-adjust` command with a stated reason  |

Note: Moderator message deletions, timeouts, kicks, and bans do **not** automatically affect score — use `/mod-adjust` for intentional penalties.

---

## Report System

- **Command:** `/report @user [reason]`
- Reason is free-form text (up to 200 characters)
- Reports are **fully anonymous** to the reported user
- A reporter can only report the same target **once per 24 hours** (rolling)
- **2 unique reports within a rolling 24h window** triggers a confirmed report:
  - Score deducted: **−300** (fixed)
  - Anonymous message posted to the configured report channel:
    `"A user has reported [Username] for: [most recent reason]"`
  - Event is logged to score history
- Mods can view all pending and processed reports via `/mod-pending-reports`

---

## Tipping System

- **Command:** `/tip @user [optional note]`
- Raises recipient's score by **+100**
- Daily tip limit is **tier-dependent** (see tier table above); resets at **00:00 GMT+2** (22:00 UTC)
- Restrictions:
  - Cannot tip yourself
  - Cannot tip bots
- Optional note is stored and shown in the recipient's score history

---

## User Commands

| Command              | Description                                              |
|----------------------|----------------------------------------------------------|
| `/score [@user]`     | Show your own or another user's score, tier, and rank    |
| `/leaderboard`       | Top 10 users by behaviour score in the server            |
| `/history [@user]`   | Last 10 score change events for any user (public)        |
| `/tip @user [note]`  | Commend a user (+100 to their score)                     |
| `/report @user [reason]` | Report a user (anonymous, free-form reason)          |
| `/server-stats`      | Server-wide score stats: average, tier distribution      |
| `/notifications`     | Toggle DM score-change notifications on or off           |

---

## Mod Commands

| Command                              | Description                                        |
|--------------------------------------|----------------------------------------------------|
| `/mod-log`                           | Recent score change events across all users        |
| `/mod-adjust @user [amount] [reason]`| Manually add or subtract score with a reason       |
| `/mod-pending-reports`               | All pending reports not yet confirmed              |

All mod commands respond **ephemerally** (visible only to the invoking mod).

---

## Automated Features

### Spam Detection
- Tracks messages per user with an in-memory sliding window
- If a user sends more than **N messages in M seconds** (configurable), −100 is applied
- The penalty can only trigger **once every 5 minutes** per user
- Defaults: 5 messages in 5 seconds

### Passive Recovery
- +5 per clock hour where the user sent at least 1 message
- Capped at **+50/day** from this source alone
- Processed by a scheduler every hour

### Reply Bonus
- +15 when another user replies to your message
- Does not trigger when replying to your own message
- Uses Discord's message reference field to detect replies

### First Message Bonus
- +20 on the user's first message of each UTC calendar day
- Tracked in daily_tracking table; resets at 00:00 GMT+2 (22:00 UTC)

### DM Notifications
- Users receive a DM when their score changes by **±200 or more** in a single event
- Users can opt out of DM notifications (preference stored in DB)

### Weekly Digest
- Posts every **Monday at 08:00 UTC** to the configured digest channel
- Contents:
  - Server average score
  - Member count per tier
  - Top 3 most-tipped users of the week
  - Biggest score gains and losses of the week

### Server Stats (`/server-stats`)
- Total members with tracked scores
- Average behaviour score
- Tier breakdown (count and %)
- Current top scorer

---

## Configuration

Stored in `.env`:

```
DISCORD_TOKEN=
GUILD_ID=
REPORT_CHANNEL_ID=       # Channel for anonymous report announcements
DIGEST_CHANNEL_ID=       # Channel for weekly digest posts
SPAM_MESSAGE_LIMIT=5     # Messages before spam penalty
SPAM_TIME_WINDOW=5       # Seconds for spam detection window
```

---

## Database Schema (SQLite via aiosqlite)

### `users`
| Column        | Type    | Notes                        |
|---------------|---------|------------------------------|
| user_id       | INTEGER | Discord user ID (PK)         |
| guild_id      | INTEGER | Discord guild ID             |
| score         | INTEGER | Current behaviour score      |
| dm_notify     | BOOLEAN | DM notification opt-in       |
| created_at    | TEXT    | ISO timestamp                |

### `score_events`
| Column    | Type    | Notes                                     |
|-----------|---------|-------------------------------------------|
| event_id  | INTEGER | Auto-increment PK                         |
| user_id   | INTEGER | FK → users                                |
| delta     | INTEGER | Score change (positive or negative)       |
| reason    | TEXT    | Human-readable description                |
| source    | TEXT    | `tip`, `report`, `mod`, `passive`, `spam`, etc. |
| timestamp | TEXT    | ISO timestamp                             |

### `reports`
| Column      | Type    | Notes                                |
|-------------|---------|--------------------------------------|
| report_id   | INTEGER | Auto-increment PK                    |
| reporter_id | INTEGER | FK → users                           |
| target_id   | INTEGER | FK → users                           |
| reason      | TEXT    | Free-form text (max 200 chars)       |
| timestamp   | TEXT    | ISO timestamp                        |
| confirmed   | BOOLEAN | Whether penalty was applied          |

### `tips`
| Column       | Type    | Notes                       |
|--------------|---------|-----------------------------|
| tip_id       | INTEGER | Auto-increment PK           |
| tipper_id    | INTEGER | FK → users                  |
| recipient_id | INTEGER | FK → users                  |
| note         | TEXT    | Optional message            |
| timestamp    | TEXT    | ISO timestamp               |

### `daily_tracking`
| Column                   | Type    | Notes                                    |
|--------------------------|---------|------------------------------------------|
| user_id                  | INTEGER | FK → users                               |
| date                     | TEXT    | GMT+2 date (YYYY-MM-DD)                  |
| tips_given               | INTEGER | Tips sent today                          |
| first_message_bonus_given| BOOLEAN | Whether +20 has been given today         |
| passive_earned_today     | INTEGER | Total passive points earned today (cap 50)|

### `reaction_tracking`
| Column     | Type    | Notes                                              |
|------------|---------|----------------------------------------------------|
| reactor_id | INTEGER | Discord user ID of the reactor                     |
| message_id | INTEGER | Discord message ID                                 |
| timestamp  | TEXT    | ISO timestamp                                      |

PK is `(reactor_id, message_id)` — prevents the same user giving +10 to the same message more than once, regardless of how many different emoji they add.
