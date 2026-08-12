#!/usr/bin/env python3
"""Stop-hook style guard for co-donde-ayudo.

Enforces the mechanical, project-specific rules from ``.claude/rules/engineering.md``
that ruff (running on defaults via the PostToolUse hook) does not cover. On Stop,
it inspects the changed Python files in the working tree and blocks the stop —
feeding the violations back to Claude — until they are fixed.

It is pure standard library and has no side effects, so it can also be invoked
directly with explicit file paths (e.g. by the ``style-guard`` subagent):

    python3 .claude/hooks/style-guard.py src/foo.py runners/bar.py

Checks (mechanical rules from .claude/rules/engineering.md not covered by ruff):
  E1  missing ``from __future__ import annotations``
  E2  retired — relative imports are enforced by ruff TID252 (ban-relative-imports=all)
  E3  retired — the bare ``*`` keyword-only separator ban was dropped (keyword-only
      parameters are a legitimate API-clarity tool)
  E4  module-level function with a leading underscore
      (methods inside a class and nested functions are allowed)
  E5  ``__init__.py`` with runtime code (only imports / __all__ / docstring)
  E6  module exceeds the 500-line hard ceiling; a ``# style-guard: E6-exempt — <reason>``
      marker in the first five lines downgrades the block to a warning
  E7  forbidden ``utils.py`` / ``utils/`` location
  E8  source package (src/) imports a CLI framework or defines a __main__ block
  E9  pydantic ``BaseSettings`` subclass defined outside core/config.py
  E10 ``os.environ`` / ``os.environ.get`` used inside a config.py instead of pydantic-settings Fields
  E11 import statement inside a function body in src/ — imports must be at the top of
      the file (.claude/rules/engineering.md); lazy-import optional dependencies with a
      module-level try/except instead
Warnings (reported, never block):
  W1  module is 300-500 lines (review whether it mixes responsibilities)
  W2  ``print()`` used in src/ (use logging instead)
  W3  try/except nested inside another try in the same function scope —
      restructure (extract helper, ``contextlib.suppress``, or ``finally``);
      see .claude/rules/engineering.md
  W5  ``ErrorCode`` enum class or ``_SAFE_REASONS`` catalog defined outside
      ``errors.py`` / ``*_errors.py`` — extract to a single errors file per
      package (.claude/rules/engineering.md)
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

CLI_FRAMEWORKS = {"click", "argparse", "typer", "rich_click", "fire"}
LINE_CEILING = 500
LINE_SOFT_LIMIT = 300
E6_EXEMPT_MARKER = "style-guard: E6-exempt"


def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def changed_python_files(root: Path) -> list[Path]:
    """Return changed/untracked .py files under src/ or runners/."""
    try:
        tracked = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=root,
        ).stdout.split()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
            cwd=root,
        ).stdout.split()
        names = tracked + untracked
    except (subprocess.CalledProcessError, FileNotFoundError):
        names = [str(p.relative_to(root)) for base in ("src", "runners") for p in (root / base).rglob("*.py")]

    files: list[Path] = []
    for name in names:
        if not name.endswith(".py"):
            continue
        if not (name.startswith("src/") or name.startswith("runners/")):
            continue
        path = root / name
        if path.is_file():
            files.append(path)
    return files


def has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(alias.name == "annotations" for alias in node.names):
                return True
    return False


def body_without_docstring(tree: ast.Module) -> list[ast.stmt]:
    body = list(tree.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return body


def find_nested_tries(tree: ast.Module) -> list[int]:
    """Line numbers of try statements nested inside another try.

    Scoped per function: a def/class boundary resets the nesting, so a try
    inside a function that is merely *defined* within a try block is not
    counted.
    """
    try_nodes = (ast.Try, ast.TryStar)
    nested: list[int] = []

    def scan(node: ast.AST, inside_try: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scan(child, False)
            elif isinstance(child, try_nodes):
                if inside_try:
                    nested.append(child.lineno)
                scan(child, True)
            else:
                scan(child, inside_try)

    scan(tree, False)
    return nested


def is_all_assignment(node: ast.stmt) -> bool:
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    return any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets)


def _is_os_environ_access(node: ast.AST) -> bool:
    """True when *node* is ``os.environ[...]`` or ``os.environ.get(...)``."""
    is_subscript = isinstance(node, ast.Subscript) and _is_os_environ_attr(node.value)
    is_get_call = (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _is_os_environ_attr(node.func.value)
    )
    return is_subscript or is_get_call


def _is_os_environ_attr(node: ast.AST) -> bool:
    """True when *node* is the ``os.environ`` Attribute."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def check_file(path: Path, root: Path) -> tuple[list[str], list[str]]:
    rel = path.relative_to(root).as_posix()
    errors: list[str] = []
    warnings: list[str] = []

    # E7: forbidden utils location (path-based, no parsing needed).
    parts = set(path.relative_to(root).parts)
    if path.name == "utils.py" or "utils" in parts:
        errors.append(f"{rel}: E7 forbidden 'utils' module/folder — use a specific domain name")

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    n = len(lines)
    e6_exempt = any(E6_EXEMPT_MARKER in line for line in lines[:5])
    if n > LINE_CEILING:
        if e6_exempt:
            warnings.append(
                f"{rel}: E6-exempt module is {n} lines (ceiling {LINE_CEILING}) — "
                f"exemption claimed, verify the stated reason still holds"
            )
        else:
            errors.append(
                f"{rel}: E6 module is {n} lines (hard ceiling {LINE_CEILING}) — split it, "
                f"or claim a documented exception with '# {E6_EXEMPT_MARKER} — <reason>' "
                f"in the first five lines (see .claude/rules/engineering.md)"
            )
    elif n > LINE_SOFT_LIMIT:
        warnings.append(f"{rel}: W1 module is {n} lines (soft limit {LINE_SOFT_LIMIT}) — review for split")

    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as exc:
        errors.append(f"{rel}: syntax error: {exc.msg} (line {exc.lineno})")
        return errors, warnings

    real_body = body_without_docstring(tree)
    in_src = rel.startswith("src/")
    is_settings_module = rel.endswith("core/config.py")
    is_config_module = rel.endswith("config.py") or rel.endswith("settings.py")

    # E1: future annotations (skip docstring-only / empty modules).
    if real_body and not has_future_annotations(tree):
        errors.append(f"{rel}: E1 missing 'from __future__ import annotations'")

    # E5: __init__.py purity.
    if path.name == "__init__.py":
        for node in real_body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if is_all_assignment(node):
                continue
            label = type(node).__name__
            errors.append(
                f"{rel}:{getattr(node, 'lineno', '?')} E5 __init__.py must contain only "
                f"imports/__all__/docstring (found {label})"
            )

    # E4: module-level underscore-prefixed functions (top level only).
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name.startswith("_") and not name.startswith("__"):
                errors.append(
                    f"{rel}:{node.lineno} E4 module-level function '{name}' has a leading "
                    f"underscore (allowed only for class methods / nested functions)"
                )

    # Walk the whole tree for the remaining per-node checks.
    # (E2 relative imports are enforced by ruff TID252; E3 was retired.)
    for node in ast.walk(tree):
        if in_src and isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in CLI_FRAMEWORKS:
                    errors.append(f"{rel}:{node.lineno} E8 src/ imports CLI framework '{alias.name}'")
        if in_src and isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in CLI_FRAMEWORKS:
                errors.append(f"{rel}:{node.lineno} E8 src/ imports CLI framework '{node.module}'")
        if in_src and isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                warnings.append(f"{rel}:{node.lineno} W2 print() in src/ — use logging")
        if isinstance(node, ast.ClassDef) and not is_settings_module:
            for base in node.bases:
                base_name = (
                    base.id
                    if isinstance(base, ast.Name)
                    else (base.attr if isinstance(base, ast.Attribute) else None)
                )
                if base_name == "BaseSettings":
                    errors.append(
                        f"{rel}:{node.lineno} E9 BaseSettings subclass '{node.name}' must live "
                        f"in core/config.py (centralized settings)"
                    )
        if is_config_module and _is_os_environ_access(node):
            errors.append(
                f"{rel}:{node.lineno} E10 raw os.environ access in config — "
                f"use pydantic-settings Field with env_file + validation_alias instead"
            )

    # W3: nested try/except within a function scope.
    for lineno in find_nested_tries(tree):
        warnings.append(
            f"{rel}:{lineno} W3 nested try/except — restructure (extract helper, "
            f"contextlib.suppress, or finally); see .claude/rules/engineering.md"
        )

    # W5: ErrorCode enum classes and _SAFE_REASONS catalog outside errors.py / *_errors.py
    # (see .claude/rules/engineering.md — one errors file per package).
    is_errors_file = path.name == "errors.py" or path.name.endswith("_errors.py")
    if not is_errors_file:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "ErrorCode" in node.name:
                warnings.append(
                    f"{rel}:{node.lineno} W5 class '{node.name}' with ErrorCode defined "
                    f"outside errors.py/*_errors.py — move to {path.parent.name}/errors.py"
                )
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign) and node.target:
                    targets = [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id == "_SAFE_REASONS":
                        warnings.append(
                            f"{rel}:{node.lineno} W5 '_SAFE_REASONS' defined outside "
                            f"errors.py/*_errors.py — move to {path.parent.name}/errors.py"
                        )

    # E8: `if __name__ == "__main__":` at module level in src/.
    if in_src:
        for node in tree.body:
            if isinstance(node, ast.If) and ast.dump(node.test).find("__main__") != -1:
                errors.append(
                    f'{rel}:{node.lineno} E8 src/ must not define an `if __name__ == "__main__"` block'
                )

    # E11: import statement inside a function body in src/.
    # .claude/rules/engineering.md: imports are always put at the top of the file.
    # Lazy-import optional dependencies with a module-level try/except instead.
    if in_src:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        errors.append(
                            f"{rel}:{child.lineno} E11 import inside function "
                            f"'{node.name}' — move to top of file "
                            f"(.claude/rules/engineering.md)"
                        )

    return errors, warnings


def main() -> int:
    # Stop-hook loop guard: never block twice in a row.
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict) and payload.get("stop_hook_active"):
            return 0
    except (json.JSONDecodeError, ValueError):
        pass

    root = repo_root()
    explicit = [Path(a) for a in sys.argv[1:]]
    files = explicit if explicit else changed_python_files(root)

    all_errors: list[str] = []
    all_warnings: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        errors, warnings = check_file(path.resolve(), root)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    if all_errors:
        reason = "Style-guard found project-rule violations (fix before stopping):\n\n"
        reason += "\n".join(f"  ✗ {e}" for e in all_errors)
        if all_warnings:
            reason += "\n\nWarnings (non-blocking):\n" + "\n".join(f"  • {w}" for w in all_warnings)
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0

    if all_warnings:
        msg = "Style-guard warnings:\n" + "\n".join(f"  • {w}" for w in all_warnings)
        print(json.dumps({"systemMessage": msg}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
