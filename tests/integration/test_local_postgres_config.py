from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LocalPostgresConfigTests(unittest.TestCase):
    def test_compose_configuration_is_valid_and_uses_pinned_postgres(self) -> None:
        validation = subprocess.run(
            ["docker", "compose", "config", "--quiet"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(validation.returncode, 0, validation.stderr)

        images = subprocess.run(
            ["docker", "compose", "config", "--images"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(images.stdout.strip(), "postgres:18.4-alpine3.23")
