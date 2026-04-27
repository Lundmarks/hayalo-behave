# Behave Bot — TODO

## Phase 1: Project Setup ✅
- [x] Initialize project structure
- [x] `requirements.txt`, `.env.example`, `config.py`
- [x] `main.py` with bot init, cog loading, scheduler start

## Phase 2: Database Layer ✅
- [x] All tables created (users, score_events, reports, tips, daily_tracking, reaction_tracking, guild_config)
- [x] Composite PKs for per-guild isolation: `(user_id, guild_id)` on users and daily_tracking
- [x] `guild_id` column on score_events, reports, tips
- [x] All helper functions implemented

## Phase 3: Core Score System ✅
- [x] New member seeded at 10,000 on join
- [x] Score clamped 0–12,000
- [x] Tier calculation
- [x] DM notifications (global per-user preference, threshold ±200)
- [x] `/notifications` toggle command

## Phase 4: Passive Gains & Interaction Bonuses ✅
- [x] First message of the day: +20 (atomic claim)
- [x] Hourly passive recovery: +5/hr, capped +50/day
- [x] Daily reset at 00:00 GMT+2 (implicit via date key)
- [x] Reactions: +10 per unique reactor per message
- [x] Replies: +30 to original author, self-replies excluded

## Phase 5: Tipping System ✅
- [x] `/tip @user [note]`
- [x] Tier-based daily limit (1–5), resets 00:00 GMT+2
- [x] Voice channel sound playback on tip
- [x] Self-tip and bot-tip blocked

## Phase 6: Report System ✅
- [x] `/report @user [reason]` (ephemeral, anonymous)
- [x] Reporter can only report the same target once per 24h rolling window; repeat attempt costs reporter −200
- [x] −300 applied immediately on each confirmed report, anonymous announcement to report channel
- [x] DM target on report

## Phase 7: Spam Detection ✅
- [x] In-memory sliding window per user
- [x] −100 on breach, 5-minute cooldown
- [x] Logged to score_events

## Phase 8: Mod Commands ✅
- [x] `/mod-adjust`, `/mod-log`, `/mod-pending-reports`
- [x] All ephemeral, gated on Manage Server permission

## Phase 9: User Commands ✅
- [x] `/score`, `/leaderboard`, `/history`, `/server-stats`

## Phase 10: Bot-Channel Enforcement ✅
- [x] `BehaviourCommandTree.interaction_check` intercepts all slash commands
- [x] −50 penalty for using commands outside configured bot channel
- [x] Exempt commands: setup, bot-check, mod-*, notifications, report

## Phase 11: Onboarding & Health Check ✅
- [x] `/setup` with native Discord channel pickers (re-runnable)
- [x] `/bot-check` verifies channels, permissions, sound file, spam config
- [x] `on_guild_join` syncs commands instantly to new servers
- [x] Multi-guild: each server has its own config and per-guild scores

## Phase 12: Weekly Digest ✅
- [x] APScheduler: Monday 08:00 Europe/Stockholm
- [x] Per-guild: iterates all configured guilds
- [x] Average score, tier breakdown, top tipped, biggest movers

## Phase 13: Polish & Release ✅
- [x] Ephemeral responses for sensitive commands
- [x] Graceful error handling throughout
- [x] `.env` reduced to token + spam config only
- [x] Docker support (Dockerfile, docker-compose.yml, .dockerignore)
- [x] README with full setup, Docker, and command reference

## Phase 14: Message Content Penalties
- [x] −score when a message consists of only a question mark (bare `?` with optional whitespace)
- [x] −score when a message contains a swear word (English and Swedish word lists in `config.py`)
  - Case-insensitive, whole-word matching to avoid false positives (e.g. "assassin")
  - Cooldown per user so rapid-fire swearing doesn't stack infinitely
  - Both penalties logged to score_events with source `message_content`
- [ ] −score when a user has reported the same target on more than N distinct calendar days (persistent targeting)
  - Tracked via a DB query on the reports table; no new table needed
  - Penalty applied to the reporter, logged with source `repeat_reporter`
