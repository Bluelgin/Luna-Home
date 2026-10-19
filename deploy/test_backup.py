"""Standalone backups contract, runnable without nanobot dependencies."""

from __future__ import annotations

import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

from backup_luna import create_backup


class BackupTest(unittest.TestCase):
    def test_memory_and_sqlite_snapshot_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / ".nanobot"
            m = root / "workspace" / "memory"
            m.mkdir(parents=True)
            (m / "MEMORY.md").write_text("test memory", encoding="utf-8")
            (root / "token.json").write_text("DO NOT BACK UP")
            sessions = root / "sessions" / "default"
            sessions.mkdir(parents=True)
            db = sessions / "sessions.sqlite3"
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE notes (name TEXT)")
                conn.execute("INSERT INTO notes VALUES ('saved')")
            output = create_backup(root, Path(temp) / "backups")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with tarfile.open(output) as archive:
                names = set(archive.getnames())
                self.assertIn("workspace/memory/MEMORY.md", names)
                self.assertIn("sessions/default/sessions.sqlite3", names)
                self.assertNotIn("token.json", names)
                self.assertEqual(
                    archive.extractfile("workspace/memory/MEMORY.md").read(),
                    b"test memory",
                )


if __name__ == "__main__":
    unittest.main()
