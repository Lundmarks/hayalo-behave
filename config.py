import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SPAM_MESSAGE_LIMIT = int(os.getenv("SPAM_MESSAGE_LIMIT", 5))
SPAM_TIME_WINDOW = int(os.getenv("SPAM_TIME_WINDOW", 5))
DATABASE_PATH = "behave.db"
TIMEZONE = "Europe/Stockholm"

SCORE_START = 10_000
SCORE_MAX = 12_000
SCORE_MIN = 0

GAIN_TIP = 100
GAIN_FIRST_MESSAGE = 20
GAIN_PASSIVE_HOURLY = 5
GAIN_PASSIVE_DAILY_CAP = 50
GAIN_REACTION = 10
GAIN_REPLY = 30

LOSS_REPORT = 300
LOSS_SPAM = 100
LOSS_BOT_CHANNEL = 50

# (min, max, label, daily_tip_limit)
TIERS = [
    (0,      2_999,  "Toxic",    1),
    (3_000,  5_999,  "Low",      2),
    (6_000,  8_999,  "Normal",   3),
    (9_000,  11_499, "Good",     4),
    (11_500, 12_000, "Pinnacle", 5),
]

DM_NOTIFY_THRESHOLD = 200
TIP_SOUND_PATH = "sounds/tip.mp3"

# Commands that bypass the bot-channel restriction
BOT_CHANNEL_EXEMPT = frozenset({
    "setup", "bot-check",
    "mod-log", "mod-adjust", "mod-pending-reports",
    "notifications", "report",
})
