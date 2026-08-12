from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectStructureTests(unittest.TestCase):
    def test_python_project_uses_separate_backend_and_frontend_packages(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["name"], "co-donde-ayudo")
        self.assertEqual(metadata["project"]["requires-python"], ">=3.12")
        self.assertEqual(metadata["project"]["scripts"]["donde-ayudo"], "frontend.runtime:run")
        self.assertNotIn("co-ayuda", metadata["project"]["scripts"])
        self.assertTrue((ROOT / "src/backend/__init__.py").is_file())
        self.assertTrue((ROOT / "src/frontend/__init__.py").is_file())


if __name__ == "__main__":
    unittest.main()
