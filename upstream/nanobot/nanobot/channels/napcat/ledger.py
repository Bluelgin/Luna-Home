"""Small SQLite message ledger to suppress OneBot replay after reconnect/restart."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class MessageLedger:
    """Durable, bounded deduplication. No message contents or QQ names stored."""

    def __init__(self, path: Path, *, ttl_seconds: int = 7 * 86400):
        self.path = path
        self.ttl_seconds = ttl_seconds
        self._inserts = 0

    def claim(self, bot_id: str, message_id: int) -> bool:
        """Return True once for each bot/message ID; fail closed on disk errors."""
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with sqlite3.connect(self.path, timeout=5) as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS processed ("
                    "bot TEXT NOT NULL, msg INTEGER NOT NULL, seen INTEGER NOT NULL, "
                    "PRIMARY KEY (bot, msg))"
                )
                now = int(time.time())
                cursor = db.execute(
                    "INSERT OR IGNORE INTO processed (bot, msg, seen) VALUES (?, ?, ?)",
                    (bot_id, message_id, now),
                )
                self._inserts += 1
                if self._inserts % 128 == 0:
                    db.execute("DELETE FROM processed WHERE seen < ?", (now - self.ttl_seconds,))
                return cursor.rowcount == 1
        except sqlite3.Error as exc:
            raise OSError("unable to use NapCat dedup SQLite store") from exc
