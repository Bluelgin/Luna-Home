#!/usr/bin/env python3
"""Offline/host preparation checks. Does not log in to QQ or OpenAI.

Usage: python3 deploy/preflight.py [--host] [--config path]
Exit nonzero only for failures of checks required in the selected mode.
"""

from __future__ import annotations

import argparse
import json
import py_compile
import shutil
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG_TEMPLATE = ROOT / "deploy" / "nanobot.config.example.json"
MODULES = [
    ROOT / "upstream/nanobot/nanobot/channels/napcat/runtime.py",
    ROOT / "upstream/nanobot/nanobot/channels/napcat/natural_chat.py",
    ROOT / "upstream/nanobot/nanobot/channels/napcat/proactive.py",
    ROOT / "upstream/nanobot/nanobot/channels/napcat/ledger.py",
    ROOT / "upstream/nanobot/nanobot/channels/napcat/media_audio.py",
    ROOT / "upstream/nanobot/nanobot/channels/napcat/piper_tts.py",
    ROOT / "persona/luna-dragon/install.py",
]


def check_config(path: Path, *, must_be_configured: bool) -> list[str]:
    errors = []
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        ch = cfg["channels"]["napcat"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"invalid config: {exc}"]
    if ch.get("privateOnly") is not True:
        errors.append("NapCat privateOnly must be true")
    owner = str(ch.get("ownerQq", ""))
    if must_be_configured and (not owner.isdigit() or not owner):
        errors.append("set ownerQq to the owner's numeric QQ account")
    allow = ch.get("allowFrom")
    if not isinstance(allow, list) or len(allow) != 1 or str(allow[0]) != owner:
        errors.append("allowFrom must exactly match ownerQq (no wildcards)")
    if ch.get("proactiveCheckinsEnabled") and not ch.get("privateOnly"):
        errors.append("proactive checkins require privateOnly")
    mins = [
        ("replyDelayMinSeconds", "replyDelayMaxSeconds"),
        ("chunkDelayMinSeconds", "chunkDelayMaxSeconds"),
    ]
    for low, high in mins:
        if not 0 <= float(ch.get(low, -1)) <= float(ch.get(high, -1)) <= 10:
            errors.append(f"invalid interval: {low}, {high}")
    url = ch.get("wsUrl")
    if not isinstance(url, str) or not url.startswith("ws://127.0.0.1:"):
        errors.append("recommended OneBot wsUrl is loopback ws://127.0.0.1:PORT")
    if not isinstance(ch.get("accessToken"), str) or not ch["accessToken"]:
        errors.append("NapCat requires an accessToken expression")
    return errors


def check_software() -> list[str]:
    errors = []
    if sys.version_info < (3, 11):
        errors.append("Python 3.11+ required")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="luna-compile-") as temp:
        for p in MODULES:
            if not p.is_file():
                errors.append(f"missing source: {p.relative_to(ROOT)}")
                continue
            try:
                py_compile.compile(str(p), cfile=str(Path(temp) / (p.stem + ".pyc")), doraise=True)
            except (OSError, py_compile.PyCompileError) as exc:
                errors.append(f"syntax: {p.name}: {exc}")
    errors.extend(check_config(CONFIG_TEMPLATE, must_be_configured=False))
    return errors


def check_host(config: Path) -> tuple[list[str], list[str]]:
    errors, notes = [], []
    errors.extend(check_config(config, must_be_configured=True))
    for tool in ("docker", "git", "ffmpeg"):
        if shutil.which(tool) is None:
            errors.append(f"missing host command: {tool}")
    # Never test or reveal tokens: using this script should not contact QQ.
    notes.append("NOT CHECKED: QQ scan/login and NapCat OneBot websocket")
    notes.append("NOT CHECKED: OpenAI OAuth / available Luna model / ASR / TTS")
    notes.append("NOT CHECKED: whether Docker image runs on your CPU architecture")
    notes.append("Ensure ports 3001 and 6099 are loopback-only, not publicly forwarded")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="store_true", help="also check Linux commands & real config")
    parser.add_argument("--config", type=Path, help="path to private nanobot config")
    args = parser.parse_args()
    errs = check_software()
    notes = []
    if args.host:
        if args.config is None:
            parser.error("--host requires --config pointing to PRIVATE config.json")
        host_errs, notes = check_host(args.config)
        errs.extend(host_errs)
    for issue in errs:
        print(f"FAIL: {issue}")
    for note in notes:
        print(f"NOTE: {note}")
    if errs:
        print(f"Preflight failed: {len(errs)} check(s).")
        return 1
    print("Preflight OK: verified locally inspectable software and configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
