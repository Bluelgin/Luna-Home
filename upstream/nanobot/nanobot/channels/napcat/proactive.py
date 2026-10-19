"""Owner-opted-in, at-most-once daily QQ check-ins.

No model tokens: these are transparent prewritten friendly check-ins, not a
simulation of having lived a separate day. Persist claims before delivery.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


GREETINGS = (
    "诶，今天怎么样呀？如果正忙的话不用回我，等你有空再聊 ww",
    "唔，突然想打个招呼。今天有没有碰到什么有趣的事情？",
    "露娜探头.jpg —— 今天有没有什么想聊的呀？嘿嘿。",
    "好耶，来看看你今天过得如何！没空的话我就安静待着啦。",
)


@dataclass(frozen=True)
class CheckinPolicy:
    timezone: str = "Asia/Shanghai"
    start_hour: int = 11
    end_hour: int = 20
    min_idle_seconds: int = 3 * 3600
    probability: float = 0.35

    def __post_init__(self) -> None:
        ZoneInfo(self.timezone)
        if not 0 <= self.start_hour < self.end_hour <= 24:
            raise ValueError("invalid proactive active-hour window")
        if self.min_idle_seconds < 0 or not 0 <= self.probability <= 1:
            raise ValueError("invalid proactive idle / probability settings")

    def local_day(self, instant: datetime) -> str:
        return instant.astimezone(ZoneInfo(self.timezone)).strftime("%Y-%m-%d")

    def eligible(self, instant: datetime, idle_seconds: float, owner_qq: str) -> bool:
        local = instant.astimezone(ZoneInfo(self.timezone))
        if not (self.start_hour <= local.hour < self.end_hour):
            return False
        if idle_seconds < self.min_idle_seconds or not owner_qq.isdigit():
            return False
        # Stable per-day draw: restart/rechecks do not eventually force a ping.
        day = local.strftime("%Y-%m-%d")
        draw = int.from_bytes(hashlib.sha256((owner_qq + ":" + day).encode()).digest()[:8],
                              byteorder="big") / 2**64
        return draw < self.probability


class CheckinLedger:
    """At-most-once daily record, separate from model memory and auth state."""

    def __init__(self, path: Path):
        self.path = path

    def claim(self, owner: str, day: str) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("CREATE TABLE IF NOT EXISTS checkins ("
                       "owner TEXT NOT NULL, day TEXT NOT NULL, "
                       "time INTEGER NOT NULL, PRIMARY KEY(owner, day))")
            result = db.execute(
                "INSERT OR IGNORE INTO checkins VALUES (?, ?, ?)",
                (owner, day, int(time.time())),
            )
            db.execute("DELETE FROM checkins WHERE time < ?", (int(time.time()) - 45*86400,))
            return result.rowcount == 1


def choose_greeting(owner: str, day: str) -> str:
    digest = hashlib.sha256((day + ":" + owner).encode()).digest()
    return GREETINGS[int.from_bytes(digest[:4], "big") % len(GREETINGS)]
