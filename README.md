# Behave Bot

A Discord bot that brings a Dota 2-style behaviour score system to your server. Every member has a score between 0 and 12,000 — starting at 10,000 — that rises through good participation and falls through toxic behaviour. Scores are per-guild, fully persistent, and visible to everyone.

---

## How it works

Every message, reaction, tip, and report feeds into a member's score:

1. Members earn points passively — first message of the day, replies received, reactions received, and hourly activity recovery
2. Members commend each other with `/tip`, adding +100 to the recipient's score
3. Members report misconduct with `/report` — each report immediately deducts −300 and posts a public announcement
4. Automated checks penalise spam, swearing, and lazy messages in real time
5. A weekly digest posts every Monday summarising the server's score distribution and top movers
6. When a tip or report targets a user in a voice channel, the bot joins and announces it with TTS

---

## Project structure

```
main.py               Bot entry point, command tree, bot-channel enforcement
config.py             All tuneable constants — scores, tiers, gains, losses, word lists
cogs/
  events.py           on_message, on_reaction_add — passive scoring and penalties
  tipping.py          /tip command and voice TTS playback
  reports.py          /report command with 24h spam-report protection
  score.py            /score, /leaderboard, /history (chart), /server-stats, /rules, /notifications
  moderation.py       /mod-log, /mod-adjust, /mod-pending-reports
  setup.py            /setup, /bot-check
db/
  database.py         SQLite layer (aiosqlite), all queries, schema definition
utils/
  scheduler.py        APScheduler — hourly passive recovery, Monday digest
  score_utils.py      Tier lookup, score bar formatter, tier colours
  state.py            In-memory spam and swear cooldown state
  voice.py            Shared voice channel TTS playback utility
sounds/
  tip.mp3             Played when a user receives a tip (provide your own)
  report.mp3          Played when a user is reported (provide your own)
data/
  behave.db           SQLite database (created on first run, gitignored)
```

---

## Setup

**Requirements:** Python 3.11+, ffmpeg

```bash
# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (required for voice)
sudo apt-get install ffmpeg   # Debian/Ubuntu
brew install ffmpeg           # macOS
```

**Create a `.env` file:**

```
DISCORD_TOKEN=your_bot_token_here
SPAM_MESSAGE_LIMIT=5
SPAM_TIME_WINDOW=5
```

**Add sound files:**

Place MP3 files at `sounds/tip.mp3` and `sounds/report.mp3`. These are played in voice channels when tips and reports are triggered. If either file is missing the bot skips that voice step silently.

**Discord Developer Portal:**

1. Go to discord.com/developers/applications and create an application
2. Under **Bot**, enable **Server Members Intent** and **Message Content Intent**
3. Under **OAuth2 → URL Generator**, select scopes `bot` and `applications.commands`
4. Required permissions: `Send Messages`, `Read Message History`, `View Channels`, `Connect`, `Speak`
5. Use the generated URL to invite the bot to your server

**Run:**

```bash
python main.py
```

Slash commands sync to all guilds on startup. On first run there are no channels configured — use `/setup` in Discord to complete setup.

**Configure in Discord:**

Run `/setup` and select your channels from the dropdowns:

- **Report channel** — where public report announcements are posted
- **Digest channel** — where the Monday weekly digest is posted
- **Bot channel** *(optional)* — restrict commands to one channel; using them elsewhere costs −50

Run `/bot-check` to verify everything is working.

---

## Running with Docker

Docker bundles ffmpeg and all dependencies — no local install needed.

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down

# Rebuild after code changes
docker compose up -d --build
```

The `data/` and `sounds/` directories are bind-mounted so the database and sound files survive rebuilds. Place your MP3 files in `sounds/` on the host before starting.

---

## Commands

### User commands

| Command | Description |
|---|---|
| `/score [@user]` | Score, tier, rank, and progress bar |
| `/leaderboard` | Top 10 scores in the server |
| `/history [@user]` | Score history chart for any user |
| `/tip @user [note]` | Commend a user (+100 to their score) |
| `/report @user [reason]` | Report a user (−300 penalty, public announcement) |
| `/server-stats` | Server-wide score statistics and tier breakdown |
| `/rules` | How the scoring system works |
| `/notifications` | Toggle DM score-change notifications on or off |

### Mod commands

| Command | Description |
|---|---|
| `/setup` | Configure channels — re-run to change |
| `/bot-check` | Verify channels, permissions, and sound files |
| `/mod-log` | 20 most recent score events across all users |
| `/mod-adjust @user [amount] [reason]` | Manual score adjustment with a logged reason |
| `/mod-pending-reports` | Reports submitted in the last 24 hours |

Mod commands require the **Manage Server** permission.

---

## Scoring

### Gains

| Source | Amount |
|---|---|
| Receiving a tip | +100 |
| Someone replies to your message | +30 |
| Receiving a ⭐ reaction | +25 |
| Receiving a 👏 or ❤️ reaction | +20 |
| Receiving a 🔥 reaction | +15 |
| Receiving any other reaction | +10 |
| First message of the day | +20 |
| Active in the last hour | +5 (max +50/day) |

### Losses

| Source | Amount |
|---|---|
| Being reported | −300 |
| Sending messages too fast | −100 |
| Swearing | −50 |
| Using bot commands outside the designated channel | −50 |
| Sending only `?` | −25 |
| Reporting the same person twice within 24 hours | −200 |

### Tiers

| Tier | Range | Tips/day |
|---|---|---|
| Toxic | 0–2,999 | 1 |
| Low | 3,000–5,999 | 2 |
| Normal | 6,000–8,999 | 3 |
| Good | 9,000–11,499 | 4 |
| Pinnacle | 11,500–12,000 | 5 |

Daily tip limits reset at 00:00 GMT+2. Tiers are cosmetic and affect tip limits only.

---

## Notes

- Scores are isolated per guild — a user's score in one server does not affect another
- Swear cooldown is 60 seconds per user — rapid-fire swearing counts as one penalty window
- Spam and swear cooldowns are in-memory and reset on bot restart
- All score changes are logged to `score_events` with a reason and source for full auditability
- The weekly digest runs every Monday at 08:00 Europe/Stockholm
