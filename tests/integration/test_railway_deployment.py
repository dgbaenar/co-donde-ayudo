from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_builds_locked_production_environment_as_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM ghcr.io/astral-sh/uv:" in dockerfile
    assert "COPY pyproject.toml uv.lock ./" in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project" in dockerfile
    assert "uv sync --frozen --no-dev" in dockerfile
    assert "USER app" in dockerfile
    assert 'CMD ["uv", "run", "--no-sync", "donde-ayudo"]' in dockerfile
    assert "alembic" not in dockerfile.lower()


def test_dockerignore_excludes_local_secrets_and_development_artifacts() -> None:
    ignored = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {".env", ".git", ".venv", ".nicegui", ".pytest_cache", "tests"} <= ignored


def test_railway_runs_migration_before_start_and_checks_readiness() -> None:
    config = (ROOT / "railway.toml").read_text(encoding="utf-8")

    assert 'builder = "DOCKERFILE"' in config
    assert (
        'preDeployCommand = ["uv run --no-sync alembic -c '
        'src/alembic/alembic.ini upgrade head"]'
    ) in config
    assert 'startCommand = "uv run --no-sync donde-ayudo"' in config
    assert 'healthcheckPath = "/readyz"' in config
    assert 'restartPolicyType = "ON_FAILURE"' in config

