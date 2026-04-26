# Behave Bot

A Discord bot that brings Dota 2's Behaviour Score system to your server.

## Features

- **Behaviour Score** (0–12,000, starting at 10,000) for every member
- **Reports** — any user can report another; each report immediately applies a −300 penalty and posts a public announcement with the reason. You can report the same person again after 24 hours; doing so within 24 hours costs you −200 for spam-reporting.
- **Tips** — commend users for +100; daily tip limit scales with your own tier; if the recipient is in a voice channel the bot joins and plays a sound
- **Passive gains** — first message of the day (+20), hourly activity (+5, capped at +50/day), reactions (+10/unique user), replies (+30)
- **Bot-channel enforcement** — optional: using commands outside the designated channel costs −50
- **Leaderboard, history, and server stats** — all public
- **Weekly digest** — every Monday 08:00 GMT+2
- **Mod tools** — `/mod-adjust`, `/mod-log`, `/mod-pending-reports`
- **Multi-server** — each server configures itself independently via `/setup`

## Setup

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Create your `.env` file

Copy `.env.example` to `.env` and fill in your bot token:

```
DISCORD_TOKEN=your_bot_token_here
SPAM_MESSAGE_LIMIT=5
SPAM_TIME_WINDOW=5
```

That is the only required value. Everything else is configured through Discord after the bot joins.

### 3. Add the tip sound

Place an MP3 file at `sounds/tip.mp3`. This is played in voice when a user receives a tip.
If missing, the bot skips the voice step silently.

ffmpeg must be installed on the host:

```bash
# Debian/Ubuntu
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

### 4. Discord Developer Portal

1. Go to https://discord.com/developers/applications and create a new application.
2. Under **Bot**, enable:
   - **Server Members Intent**
   - **Message Content Intent**
3. Under **OAuth2 → URL Generator**, select scopes: `bot`, `applications.commands`.
   Permissions: `Send Messages`, `Read Message History`, `View Channels`, `Connect`, `Speak`.
4. Use the generated URL to invite the bot to your server.

### 5. Run the bot

```bash
python main.py
```

Slash commands are synced to your guild instantly on startup and whenever the bot joins a new server.

### 6. Configure the bot in Discord

Run `/setup` in any channel and pick your channels from the dropdowns:

- **Report channel** — where report announcements are posted publicly
- **Digest channel** — where the Monday weekly digest is posted
- **Bot channel** *(optional)* — restrict all bot commands to one channel (costs −50 if used elsewhere)

Run `/bot-check` to verify everything is green.

---

## Running with Docker

Docker bundles ffmpeg and all dependencies — no local Python or ffmpeg install needed.

### Build and start

```bash
docker compose up -d --build
```

### View logs

```bash
docker compose logs -f
```

### Stop the bot

```bash
docker compose down
```

### Rebuild after code changes

```bash
docker compose up -d --build
```

**Notes:**
- `.env` is read from the project root via `env_file`.
- `behave.db` and `sounds/` are mounted as volumes so they survive rebuilds.
- Place `tip.mp3` in the `sounds/` directory on the host before starting.

---

## Commands

| Command | Description |
|---|---|
| `/score [@user]` | View score, tier, rank, and progress bar |
| `/leaderboard` | Top 10 scores in the server |
| `/history [@user]` | Last 10 score events for any user |
| `/tip @user [note]` | Commend a user (+100 to their score) |
| `/report @user [reason]` | Report a user (−300 to their score, public announcement) |
| `/server-stats` | Server-wide score statistics |
| `/notifications` | Toggle DM score-change notifications |
| `/setup` | *(Mod)* Configure channels — re-run to change |
| `/bot-check` | *(Mod)* Verify the bot configuration |
| `/mod-log` | *(Mod)* Recent score events |
| `/mod-adjust @user [amount] [reason]` | *(Mod)* Manual score adjustment |
| `/mod-pending-reports` | *(Mod)* Reports submitted in the last 24 h |

Mod commands require the **Manage Server** permission.

## Tiers

| Tier | Score Range | Tips/Day |
|---|---|---|
| Toxic | 0–2,999 | 1 |
| Low | 3,000–5,999 | 2 |
| Normal | 6,000–8,999 | 3 |
| Good | 9,000–11,499 | 4 |
| Pinnacle | 11,500–12,000 | 5 |

Daily tip counters reset at **00:00 GMT+2**.
