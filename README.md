<div align="center">

```
  ██╗  ██╗ █████╗ ██╗   ██╗ █████╗ ██╗      ██████╗ 
  ██║  ██║██╔══██╗╚██╗ ██╔╝██╔══██╗██║     ██╔═══██╗
  ███████║███████║ ╚████╔╝ ███████║██║     ██║   ██║
  ██╔══██║██╔══██║  ╚██╔╝  ██╔══██║██║     ██║   ██║
  ██║  ██║██║  ██║   ██║   ██║  ██║███████╗╚██████╔╝
  ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝
  ██████╗ ███████╗██╗  ██╗ █████╗ ██╗   ██╗███████╗
  ██╔══██╗██╔════╝██║  ██║██╔══██╗██║   ██║██╔════╝
  ██████╔╝█████╗  ███████║███████║██║   ██║█████╗  
  ██╔══██╗██╔══╝  ██╔══██║██╔══██║╚██╗ ██╔╝██╔══╝  
  ██████╔╝███████╗██║  ██║██║  ██║ ╚████╔╝ ███████╗
  ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝
```

**Dota 2-style behaviour score for your Discord server**  
*Commend good members. Report the bad ones. Let the numbers do the talking.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![SQLite](https://img.shields.io/badge/SQLite-aiosqlite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

</div>

---

## What is this?

**Hayalo Behave** is a Discord bot that gives every member a behaviour score between 0 and 12,000 — starting at 10,000. Good participation earns points. Toxic behaviour loses them. The whole server can see everyone's score at any time.

It works like Dota 2's behaviour score system: passive gains for activity, commendations from peers, and reports that hit hard and fast.

> Scores are per-guild and fully persistent.  
> Nothing carries over between servers.

---

## How it works

```
  SCORE PIPELINE
  ──────────────────────────────────────────────────────────────
  Activity  →  Passive gains  →  Peer tips/reports  →  Score change  →  Public log
```

| Trigger | Effect |
|---|---|
| First message of the day | +20 |
| Active in the last hour | +5 (max +50/day) |
| Receiving a reply | +30 |
| Receiving a reaction | +10–25 depending on type |
| Someone tips you `/tip` | +100 |
| Someone reports you `/report` | −300 + public announcement |
| Spamming messages | −100 |
| Swearing | −50 |
| Using bot commands outside the designated channel | −50 |
| Sending only `?` | −25 |
| Reporting the same person twice in 24 hours | −200 to the reporter |

A weekly digest posts every Monday summarising score distribution and top movers. When a tip or report targets someone in a voice channel, the bot pre-generates TTS audio and then joins to announce it immediately — using ElevenLabs neural voices if configured, falling back to Google TTS otherwise.

---

## Installation

### Prerequisites — FFmpeg

FFmpeg is required for voice TTS announcements.

| OS | Command |
|---|---|
| **Debian / Ubuntu / WSL** | `sudo apt-get install ffmpeg` |
| **macOS** | `brew install ffmpeg` |

Verify with: `ffmpeg -version`

---

### 1 · Clone the repository

```bash
git clone https://github.com/lundmarks/hayalo-behave.git
cd hayalo-behave
```

---

### 2 · Install dependencies

```bash
pip install -r requirements.txt
```

---

### 3 · Configure your credentials

Create a `.env` file:

```env
DISCORD_TOKEN=your_bot_token_here
SPAM_MESSAGE_LIMIT=5
SPAM_TIME_WINDOW=5
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_IDS=voice_id_1,voice_id_2,voice_id_3
TIP_REPORT_CHAR_LIMIT=50
```

`ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_IDS` are optional. If omitted, TTS falls back to Google TTS (gTTS) automatically. `TIP_REPORT_CHAR_LIMIT` controls the maximum character length for tip notes and report reasons (default: 50). To get ElevenLabs values:

1. Sign up at [elevenlabs.io](https://elevenlabs.io) and copy your API key from **Profile → API Keys**
2. Find a voice in the voice library, open it, and copy the voice ID from the URL or detail page
3. Add one or more comma-separated voice IDs — a random one is picked for each announcement

> **Note:** Community/library voices require a paid ElevenLabs subscription. The default pre-made voices (e.g. `Adam`, `Rachel`) work on the free tier. If the API call fails for any reason, TTS silently falls back to gTTS.

---

### 4 · Add sound files

Place MP3 files at `sounds/tip.mp3` and `sounds/report.mp3`. These play in voice channels when tips and reports are triggered. If either file is missing, that voice step is skipped silently.

---

### 5 · Set up the Discord application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and create an application
2. Under **Bot**, enable **Server Members Intent** and **Message Content Intent**
3. Under **OAuth2 → URL Generator**, select scopes `bot` and `applications.commands`
4. Required permissions: `Send Messages` · `Read Message History` · `View Channels` · `Connect` · `Speak`
5. Use the generated URL to invite the bot to your server

---

### 6 · Run

```bash
python main.py
```

Slash commands sync to all guilds on startup. On first run, no channels are configured — use `/setup` in Discord to complete setup.

---

### 7 · Configure in Discord

Run `/setup` and select your channels from the dropdowns:

- **Report channel** — where public report announcements are posted
- **Digest channel** — where the Monday weekly digest is posted
- **Bot channel** *(optional)* — restrict commands to one channel; using them elsewhere costs −50

Run `/bot-check` to verify everything is working.

---

## Running with Docker

Docker bundles FFmpeg and all dependencies — no local install needed.

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
| `/tip @user <note>` | Commend a user (+100 to their score) — note required, max 50 characters |
| `/report @user <reason>` | Report a user (−300 penalty, public announcement) — max 50 characters |
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

## Project structure

```
main.py               Bot entry point, command tree, bot-channel enforcement
config.py             All tuneable constants — scores, tiers, gains, losses, word lists
cogs/
  events.py           on_message, on_reaction_add — passive scoring and penalties
  tipping.py          /tip command and voice TTS playback
  reports.py          /report command with 24h spam-report protection
  score.py            /score, /leaderboard, /history, /server-stats, /rules, /notifications
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

## Notes

- Scores are isolated per guild — a user's score in one server does not affect another
- Swear cooldown is 60 seconds per user — rapid-fire swearing counts as one penalty window
- Spam and swear cooldowns are in-memory and reset on bot restart
- Score events are kept for 8 days and then pruned automatically — tip and report history is kept forever
- The weekly digest runs every Monday at 08:00 Europe/Stockholm

---

## Requirements

- Python 3.11+
- FFmpeg (system install)
- Discord bot token
- ElevenLabs API key + voice ID *(optional — falls back to gTTS if not set)*

---

## License

MIT

---

<div align="center">
<sub>discord.py · aiosqlite · APScheduler · FFmpeg · ElevenLabs · gTTS</sub>
</div>
