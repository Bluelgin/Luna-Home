#!/usr/bin/env python3
"""Safely install Luna's SOUL.md into a nanobot workspace.

Default is dry-run. Never edits USER.md, MEMORY.md, sessions, Dream data,
config.json or secrets. Existing SOUL.md is backed up only with --replace.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SOURCE = Path(__file__).with_name("SOUL.md")


def install(workspace: Path, *, apply: bool = False, replace: bool = False) -> str:
    """Return a status message. Raises on unsafe paths/incorrect flags."""
    if replace and not apply:
        raise ValueError("--replace requires --apply")
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Missing bundled persona: {SOURCE}")

    workspace = workspace.expanduser()
    dest = workspace / "SOUL.md"
    if dest.is_symlink():
        raise ValueError("Refusing to write to a symlink SOUL.md")

    content = SOURCE.read_bytes()
    if dest.exists():
        if not dest.is_file():
            raise ValueError("SOUL.md exists but is not a regular file")
        if dest.read_bytes() == content:
            return f"Already current: {dest}"
        if not replace:
            return f"Existing SOUL.md left untouched: {dest} (use --apply --replace to back up and replace)"
    if not apply:
        return f"DRY RUN: would {'back up and replace' if dest.exists() else 'create'} {dest}"

    workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    if dest.exists():
        backups = workspace / ".luna-soul-backups"
        if backups.is_symlink():
            raise ValueError("Refusing to use symlink backup directory")
        backups.mkdir(mode=0o700, exist_ok=True)
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backups / f"SOUL-{suffix}-{uuid4().hex[:8]}.md"
        shutil.copyfile(dest, backup)
        backup.chmod(0o600)

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".SOUL-", dir=workspace, delete=False
        ) as tmp:
            temp_name = tmp.name
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, dest)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
    return f"Installed Luna persona: {dest} (restart gateway to activate)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path,
        default=Path.home() / ".nanobot" / "workspace",
        help="nanobot agent workspace, NOT your GitHub checkout",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="write the SOUL.md; omitted means only a preview",
    )
    parser.add_argument(
        "--replace", action="store_true",
        help="back up and replace existing SOUL.md (requires --apply)",
    )
    args = parser.parse_args()
    try:
        print(install(args.workspace, apply=args.apply, replace=args.replace))
    except (OSError, ValueError) as exc:
        parser.exit(status=2, message=f"ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
