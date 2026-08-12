#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tomllib


PROTECTED_PATH = re.compile(
    r"(?:^|[/\\\s'\"=:])(?:CLAUDE\.md|\.claude(?:[/\\]|$))",
    re.IGNORECASE,
)
WRITE_LIKE_SHELL = re.compile(
    r"(?:^|[;&|]\s*)(?:rm|mv|cp|rsync|install|chmod|chown|patch|tee|truncate|touch)\b|"
    r"\bgit\s+(?:restore|checkout|clean)\b|\bsed\s+-i\b|\bperl\s+-pi\b|"
    r"\b(?:write_text|write_bytes|unlink|rename|replace)\s*\(",
    re.IGNORECASE,
)
FRONTMATTER = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
SECRET_ASSIGNMENT = re.compile(
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{12,}['\"]",
    re.IGNORECASE,
)


def _tool_name(payload: dict[str, object]) -> str:
    value = payload.get("tool_name", payload.get("toolName", ""))
    return value if isinstance(value, str) else ""


def _tool_text(payload: dict[str, object]) -> str:
    tool_input = payload.get("tool_input", payload.get("toolInput", {}))
    if not isinstance(tool_input, dict):
        return ""
    parts = [value for value in tool_input.values() if isinstance(value, str)]
    return "\n".join(parts)


def pretool_decision(payload: dict[str, object]) -> dict[str, object] | None:
    """Deny write-capable tool calls that target the preserved source harness."""
    name = _tool_name(payload).lower()
    text = _tool_text(payload)
    if not PROTECTED_PATH.search(text):
        return None

    direct_write = name in {"apply_patch", "edit", "write"}
    shell_write = name in {"bash", "shell", "exec_command"} and bool(
        WRITE_LIKE_SHELL.search(text)
    )
    if not (direct_write or shell_write):
        return None

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "The source harness is immutable. Write only to the separate Codex harness."
            ),
        }
    }


def _read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read {path}: {exc}")
        return ""


def validate_harness(root: Path) -> list[str]:
    """Return structural and isolation errors without changing the filesystem."""
    root = root.resolve()
    errors: list[str] = []
    agents_file = root / "AGENTS.md"
    config_file = root / ".codex/config.toml"
    agent_dir = root / ".codex/agents"
    rule_dir = root / ".codex/rules"
    skill_dir = root / ".agents/skills"

    for path in (agents_file, config_file, agent_dir, rule_dir, skill_dir):
        if not path.exists():
            errors.append(f"missing required harness path: {path.relative_to(root)}")

    if errors:
        return errors

    index = _read_text(agents_file, errors)
    try:
        tomllib.loads(_read_text(config_file, errors))
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"invalid TOML in .codex/config.toml: {exc}")

    agent_paths = sorted(agent_dir.glob("*.toml"))
    if not agent_paths:
        errors.append("no custom agent definitions found")
    for path in agent_paths:
        text = _read_text(path, errors)
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"invalid TOML in {path.relative_to(root)}: {exc}")
            continue
        missing = {"name", "description", "developer_instructions"} - data.keys()
        if missing:
            errors.append(f"{path.relative_to(root)} missing keys: {sorted(missing)}")
        if data.get("name") != path.stem:
            errors.append(f"{path.relative_to(root)} name must match its filename")
        if data.get("sandbox_mode") not in {"read-only", "workspace-write"}:
            errors.append(f"{path.relative_to(root)} has unsupported sandbox_mode")

    rule_paths = sorted(rule_dir.glob("*.md"))
    if not rule_paths:
        errors.append("no detailed rules found")
    for path in rule_paths:
        relative = path.relative_to(root).as_posix()
        text = _read_text(path, errors)
        if relative not in index:
            errors.append(f"AGENTS.md does not reference {relative}")
    skill_paths = sorted(skill_dir.glob("*/SKILL.md"))
    if not skill_paths:
        errors.append("no skills found")
    for path in skill_paths:
        relative = path.relative_to(root).as_posix()
        text = _read_text(path, errors)
        match = FRONTMATTER.match(text)
        if not match:
            errors.append(f"{relative} is missing YAML frontmatter")
            continue
        metadata = match.group("body")
        name_match = re.search(r"^name:\s*(\S+)\s*$", metadata, re.MULTILINE)
        description_match = re.search(
            r"^description:\s*(.+?)\s*$", metadata, re.MULTILINE
        )
        if not name_match or name_match.group(1) != path.parent.name:
            errors.append(f"{relative} has an invalid skill name")
        if not description_match or not description_match.group(1).startswith("Use when"):
            errors.append(f"{relative} description must start with 'Use when'")
        openai_file = path.parent / "agents/openai.yaml"
        if not openai_file.is_file():
            errors.append(f"{relative} is missing agents/openai.yaml")
        else:
            openai_text = _read_text(openai_file, errors)
            expected_invocation = f"${path.parent.name}"
            if expected_invocation not in openai_text:
                errors.append(
                    f"{openai_file.relative_to(root)} default prompt must mention "
                    f"{expected_invocation}"
                )

    harness_files = [agents_file, *agent_paths, *rule_paths]
    harness_files.extend(path for path in skill_dir.rglob("*") if path.is_file())
    for path in harness_files:
        text = _read_text(path, errors)
        if SECRET_ASSIGNMENT.search(text):
            errors.append(f"possible embedded secret in {path.relative_to(root)}")

    hooks_file = root / ".codex/hooks.json"
    if hooks_file.exists():
        try:
            json.loads(_read_text(hooks_file, errors))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in .codex/hooks.json: {exc}")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--validate"]:
        errors = validate_harness(Path.cwd())
        if errors:
            for error in errors:
                print(f"project harness: FAIL: {error}", file=sys.stderr)
            return 1
        print("project harness: PASS")
        return 0
    if args:
        print("usage: project_guard.py [--validate]", file=sys.stderr)
        return 2
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"invalid hook input: {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("invalid hook input: expected an object", file=sys.stderr)
        return 1
    decision = pretool_decision(payload)
    if decision is not None:
        print(json.dumps(decision, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
