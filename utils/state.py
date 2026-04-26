from collections import defaultdict, deque

# Sliding-window message timestamps per user for spam detection
message_timestamps: dict[int, deque] = defaultdict(deque)

# Timestamp of last spam penalty per user (unix seconds)
spam_cooldowns: dict[int, float] = {}

# (user_id, guild_id) pairs that sent at least one message this hour
active_this_hour: set[tuple[int, int]] = set()
