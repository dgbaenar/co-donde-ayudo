from __future__ import annotations

import ast
from pathlib import Path


def test_source_packages_use_only_absolute_imports() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    relative_imports = []

    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                relative_imports.append(f"{path.relative_to(source_root)}:{node.lineno}")

    assert not relative_imports, f"relative imports are prohibited: {', '.join(relative_imports)}"
