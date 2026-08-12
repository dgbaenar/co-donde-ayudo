from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("project_guard.py")
SPEC = importlib.util.spec_from_file_location("project_guard", MODULE_PATH)
assert SPEC and SPEC.loader
project_guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_guard)


class ProjectGuardTests(unittest.TestCase):
    def test_pretool_denies_patch_targeting_protected_harness(self) -> None:
        payload = {
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: .claude/settings.json"},
        }
        decision = project_guard.pretool_decision(payload)
        self.assertEqual(
            decision["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_pretool_allows_patch_targeting_codex_harness(self) -> None:
        payload = {
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: .codex/config.toml"},
        }
        self.assertIsNone(project_guard.pretool_decision(payload))

    def test_pretool_denies_shell_mutations_targeting_protected_harness(self) -> None:
        commands = (
            "git restore CLAUDE.md",
            "git checkout -- CLAUDE.md",
            "rsync source/ .claude/",
            "install source .claude/settings.json",
            "chmod 600 CLAUDE.md",
            "patch CLAUDE.md change.patch",
        )
        for command in commands:
            with self.subTest(command=command):
                payload = {"tool_name": "Bash", "tool_input": {"command": command}}
                decision = project_guard.pretool_decision(payload)
                self.assertEqual(
                    decision["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_validate_accepts_complete_temp_harness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_valid_harness(root)
            self.assertEqual(project_guard.validate_harness(root), [])

    def test_validate_rejects_invalid_agent_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_valid_harness(root)
            (root / ".codex/agents/worker.toml").write_text("name = [", encoding="utf-8")
            errors = project_guard.validate_harness(root)
            self.assertTrue(any("invalid TOML" in error for error in errors))

    def test_validate_rejects_skill_without_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_valid_harness(root)
            (root / ".agents/skills/example/SKILL.md").write_text(
                "# Missing metadata\n", encoding="utf-8"
            )
            errors = project_guard.validate_harness(root)
            self.assertTrue(any("frontmatter" in error for error in errors))

    def test_validate_rejects_skill_prompt_without_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_valid_harness(root)
            (root / ".agents/skills/example/agents/openai.yaml").write_text(
                'interface:\n  default_prompt: "Use the skill."\n',
                encoding="utf-8",
            )
            errors = project_guard.validate_harness(root)
            self.assertTrue(any("$example" in error for error in errors))

    @staticmethod
    def _write_valid_harness(root: Path) -> None:
        (root / ".codex/agents").mkdir(parents=True)
        (root / ".codex/rules").mkdir(parents=True)
        (root / ".agents/skills/example").mkdir(parents=True)
        (root / "AGENTS.md").write_text(
            "# Guidance\n\n.codex/rules/engineering.md\n", encoding="utf-8"
        )
        (root / ".codex/config.toml").write_text(
            "[agents]\nenabled = true\n", encoding="utf-8"
        )
        (root / ".codex/agents/worker.toml").write_text(
            'name = "worker"\n'
            'description = "Use for bounded work."\n'
            'sandbox_mode = "read-only"\n'
            'developer_instructions = "Inspect and report."\n',
            encoding="utf-8",
        )
        (root / ".codex/rules/engineering.md").write_text(
            "# Engineering\n", encoding="utf-8"
        )
        (root / ".agents/skills/example/SKILL.md").write_text(
            "---\nname: example\ndescription: Use when testing.\n---\n\n# Example\n",
            encoding="utf-8",
        )
        (root / ".agents/skills/example/agents").mkdir()
        (root / ".agents/skills/example/agents/openai.yaml").write_text(
            json.dumps(
                {
                    "interface": {
                        "display_name": "Example",
                        "default_prompt": "Use $example to test.",
                    }
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
