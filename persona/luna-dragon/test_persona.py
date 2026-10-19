"""Offline persona contract tests: no LLM token/API key needed."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PERSONA_DIR = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("luna_persona_installer", PERSONA_DIR / "install.py")
assert SPEC is not None and SPEC.loader is not None
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class LunaPersonaTests(unittest.TestCase):
    def test_dry_run_does_not_touch_workspace(self):
        with tempfile.TemporaryDirectory() as base:
            workspace = Path(base) / "new" / "workspace"
            result = mod.install(workspace)
            self.assertIn("DRY RUN", result)
            self.assertFalse(workspace.exists())

    def test_explicit_install_and_idempotence(self):
        with tempfile.TemporaryDirectory() as base:
            workspace = Path(base) / "workspace"
            result = mod.install(workspace, apply=True)
            self.assertIn("Installed", result)
            self.assertEqual((workspace / "SOUL.md").read_bytes(), mod.SOURCE.read_bytes())
            self.assertIn("Already current", mod.install(workspace, apply=True))
            self.assertFalse((workspace / ".luna-soul-backups").exists())

    def test_non_overwrite_and_backup_before_replacement(self):
        with tempfile.TemporaryDirectory() as base:
            workspace = Path(base) / "workspace"
            workspace.mkdir()
            (workspace / "SOUL.md").write_text("# Existing soul\n", encoding="utf-8")
            (workspace / "USER.md").write_text("private user preferences", encoding="utf-8")
            self.assertIn("left untouched", mod.install(workspace, apply=True))
            self.assertEqual((workspace / "SOUL.md").read_text(), "# Existing soul\n")
            self.assertIn("back up and replace", mod.install(workspace))
            self.assertIn("Installed", mod.install(workspace, apply=True, replace=True))
            backups = list((workspace / ".luna-soul-backups").glob("SOUL-*.md"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "# Existing soul\n")
            self.assertEqual((workspace / "USER.md").read_text(), "private user preferences")

    def test_replace_requires_apply_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as base:
            workspace = Path(base) / "workspace"
            workspace.mkdir()
            with self.assertRaisesRegex(ValueError, "requires"):
                mod.install(workspace, replace=True)
            source = workspace / "real.md"
            source.write_text("original")
            (workspace / "SOUL.md").symlink_to(source)
            with self.assertRaisesRegex(ValueError, "symlink"):
                mod.install(workspace, apply=True, replace=True)

    def test_compatible_character_card(self):
        card = json.loads((PERSONA_DIR / "character_card_v2.json").read_text(encoding="utf-8"))
        self.assertEqual(card["spec"], "chara_card_v2")
        self.assertEqual(card["spec_version"], "2.0")
        fields = {"name", "description", "personality", "scenario",
                  "first_mes", "mes_example", "creator_notes", "system_prompt",
                  "post_history_instructions", "alternate_greetings",
                  "tags", "creator", "character_version", "extensions"}
        self.assertTrue(fields.issubset(card["data"]))
        self.assertTrue(card["data"]["alternate_greetings"])
        self.assertEqual(card["data"]["extensions"]["luna_home"]["official_character"], False)

    def test_soul_covers_core_behavior(self):
        soul = mod.SOURCE.read_text(encoding="utf-8")
        for phrase in ["呆萌", "学习", "开发", "AI", "QQ", "不编造", "记忆", "不诱导排他依赖"]:
            self.assertIn(phrase, soul)


if __name__ == "__main__":
    unittest.main()
