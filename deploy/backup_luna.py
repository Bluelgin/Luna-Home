"""Consistent local backups of Luna memory and SQLite without copying credentials.

Archives still contain PRIVATE conversational data. Keep 0600 and encrypt before
transferring off-host. No media, OAuth tokens or QQ login profiles are included.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def create_backup(home: Path, destination: Path, keep: int = 7) -> Path:
    source = home.expanduser().resolve()
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination, 0o700)
    date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination / f"luna-memory-{date}.tar.gz"
    with tempfile.TemporaryDirectory(prefix=".luna-", dir=destination) as temp:
        staging = Path(temp)
        with tarfile.open(staging / "archive.tar.gz", "w:gz") as archive:
            # Preserve stable persona/memory only; no raw message media.
            workspace = source / "workspace"
            paths = [
                workspace / "SOUL.md",
                workspace / "USER.md",
                workspace / "memory" / "MEMORY.md",
                workspace / "memory" / "history.jsonl",
            ]
            for path in paths:
                if path.is_file() and not path.is_symlink():
                    archive.add(path, arcname=f"workspace/{path.relative_to(workspace)}")
            # Snapshot SQLite through backup() to be safe against active writers.
            for db_path in source.rglob("*.sqlite3"):
                if not db_path.is_file() or db_path.is_symlink():
                    continue
                rel = db_path.relative_to(source)
                # Only persist conversations. Exclude other SQLite databases
                # (OAuth, pairing, job queues, credentials and NapCat dedup).
                if "sessions" not in rel.parts:
                    continue
                with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as src:
                    snapshot = staging / ("snapshot-" + str(len(list(staging.iterdir()))) + ".sqlite3")
                    with sqlite3.connect(snapshot) as dst:
                        src.backup(dst)
                    archive.add(snapshot, arcname=str(rel))
        os.chmod(staging / "archive.tar.gz", 0o600)
        os.replace(staging / "archive.tar.gz", target)

    existing = sorted(destination.glob("luna-memory-*.tar.gz"), reverse=True)
    for old in existing[max(1, keep):]:
        old.unlink(missing_ok=True)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home() / ".nanobot")
    parser.add_argument("--destination", type=Path, default=Path.home() / "backups")
    parser.add_argument("--keep", type=int, default=7)
    args = parser.parse_args()
    result = create_backup(args.home, args.destination, args.keep)
    print(f"Local private memory snapshot: {result}")
