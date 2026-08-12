# Phase 1 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the usable Phase 1 web flow with responsive desktop/mobile presentation and a reproducible local PostgreSQL environment that can be replaced by Supabase through `DATABASE_URL` only.

**Architecture:** Docker Compose owns only local PostgreSQL. Alembic owns schema creation, SQLAlchemy/Psycopg own persistence, and NiceGUI owns presentation. Local and Supabase environments share the same application composition and differ only in environment values.

**Tech Stack:** Python >=3.12 (verified with 3.14.2), NiceGUI 3.15.0, SQLAlchemy 2.0.51, Psycopg 3.3.4, Alembic 1.18.5, python-dotenv 1.2.2, PostgreSQL 18.4 Alpine 3.23, Docker Compose, pytest 9.1.1.

## Global Constraints

- Use absolute imports rooted at `backend` or `frontend`; relative imports are prohibited.
- Keep backend, frontend, local infrastructure, and documentation responsibilities separate.
- Do not add a PWA, native app, map, endpoint, table, or deployment boundary.
- Do not read, print, or commit real credentials. Local defaults are development-only values.
- Do not modify `CLAUDE.md` or `.claude/**`.
- Do not stage, commit, push, or mutate Git.
- Observe RED before production changes and run the scoped test after each task.

---

### Task 1: Reproducible local PostgreSQL and environment loading

**Files:**
- Create: `compose.yaml`
- Modify: `.env.example`
- Modify: `src/frontend/runtime.py`
- Modify: `tests/frontend/test_runtime.py`
- Create: `tests/integration/test_local_postgres_config.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `DatabaseConfig.from_environment(environ)` and `src/alembic/alembic.ini`.
- Produces: `postgres` Compose service on `127.0.0.1:5432`, persistent `postgres_data` volume, and runtime `.env` loading before reading `os.environ`.

- [ ] **Step 1: Add failing runtime and Compose tests**

```python
def test_run_loads_dotenv_before_building_runtime():
    runtime = self.import_runtime()
    calls = []
    with (
        patch.object(runtime, "load_dotenv", side_effect=lambda: calls.append("dotenv")),
        patch.object(runtime, "build_runtime", side_effect=lambda environ: calls.append("build")),
        patch.object(runtime.ui, "run", side_effect=lambda: calls.append("run")),
    ):
        runtime.run()
    self.assertEqual(calls, ["dotenv", "build", "run"])

def test_compose_configuration_is_valid_and_uses_pinned_postgres():
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
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/frontend/test_runtime.py tests/integration/test_local_postgres_config.py -q`

Expected: FAIL because `load_dotenv` and `compose.yaml` are absent.

- [ ] **Step 3: Add the local PostgreSQL service**

```yaml
services:
  postgres:
    image: postgres:18.4-alpine3.23
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-donde_ayudo}
      POSTGRES_USER: ${POSTGRES_USER:-donde_ayudo}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-donde_ayudo_local}
    ports:
      - "127.0.0.1:${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 2s
      timeout: 5s
      retries: 15
    volumes:
      - postgres_data:/var/lib/postgresql

volumes:
  postgres_data:
```

- [ ] **Step 4: Load `.env` at the runtime boundary**

```python
from dotenv import load_dotenv

def run() -> None:
    load_dotenv()
    build_runtime(os.environ)
    ui.run()
```

- [ ] **Step 5: Document local defaults and commands**

`.env.example` must include:

```dotenv
DATABASE_URL=postgresql://donde_ayudo:donde_ayudo_local@localhost:5432/donde_ayudo
APP_BASE_URL=http://localhost:8080
POSTGRES_DB=donde_ayudo
POSTGRES_USER=donde_ayudo
POSTGRES_PASSWORD=donde_ayudo_local
POSTGRES_PORT=5432
```

README commands must be, in order:

```bash
cp .env.example .env
docker compose up -d postgres
uv run alembic -c src/alembic/alembic.ini upgrade head
uv run donde-ayudo
```

- [ ] **Step 6: Verify GREEN**

Run: `uv run pytest tests/frontend/test_runtime.py tests/integration/test_local_postgres_config.py -q`

Expected: PASS.

---

### Task 2: Responsive public, creation, and administration pages

**Files:**
- Modify: `src/frontend/pages/home.py`
- Modify: `src/frontend/pages/create_help_point.py`
- Modify: `src/frontend/pages/manage_help_point.py`
- Modify: `tests/frontend/test_home.py`
- Modify: `tests/frontend/test_create_help_point.py`
- Modify: `tests/frontend/test_manage_help_point.py`

**Interfaces:**
- Consumes: existing `Mapping[str, UUID]`, `NeedStatus`, and injected handlers.
- Produces: visible `/crear` CTA, explicit empty state, full-width touch controls, category labels, and a selector-driven status update.

- [ ] **Step 1: Add failing behavioral tests**

```python
def test_category_name_resolves_known_id_and_falls_back():
    assert category_name({"Agua": water_id}, water_id) == "Agua"
    assert category_name({}, water_id) == "Necesidad"

def test_status_options_use_public_spanish_labels():
    assert status_options() == {
        "Se necesita": NeedStatus.NEEDS_HELP,
        "Hay ayuda en camino": NeedStatus.HELP_ON_THE_WAY,
        "Cubierto": NeedStatus.COVERED,
    }
```

Add render-level tests using a small recording NiceGUI fake to assert the `/crear` link, empty-state label, responsive container class, full-width fields, and `min-h-[44px]` actions.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/frontend/test_home.py tests/frontend/test_create_help_point.py tests/frontend/test_manage_help_point.py -q`

Expected: FAIL because the responsive behavior and helpers are absent.

- [ ] **Step 3: Implement Home and creation presentation**

Use `w-full max-w-md md:max-w-2xl mx-auto gap-3 p-4` for page containers. Add `ui.link("Crear punto de ayuda", "/crear")`, apply `w-full` to fields, and show `No hay puntos que coincidan con estos filtros.` when filtered results are empty. Apply `w-full min-h-[44px]` to primary actions.

- [ ] **Step 4: Implement administration presentation**

```python
def category_name(categories: Mapping[str, UUID], category_id: UUID) -> str:
    return next((name for name, current_id in categories.items() if current_id == category_id), "Necesidad")

def status_options() -> dict[str, NeedStatus]:
    return {
        "Se necesita": NeedStatus.NEEDS_HELP,
        "Hay ayuda en camino": NeedStatus.HELP_ON_THE_WAY,
        "Cubierto": NeedStatus.COVERED,
    }
```

Each card shows category name and public status text, then a full-width state select and `Guardar estado` button. Add/remove/save/deactivate actions remain wired to the existing handlers.

- [ ] **Step 5: Verify GREEN**

Run: `uv run pytest tests/frontend -q`

Expected: PASS.

---

### Task 3: Local PostgreSQL round-trip and Phase 1 gate

**Files:**
- Create: `tests/integration/test_postgres_round_trip.py`
- Modify: `docs/product/backlog.md`
- Modify: `docs/product/mvp.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: running Compose `postgres`, Alembic migration, `create_session_factory`, `PostgresHelpPointRepository`, and `HelpPointService`.
- Produces: a real local database round-trip proving create, public listing, admin lookup, status change, need removal, and deactivation.

- [ ] **Step 1: Start the approved local service**

Run: `docker compose up -d postgres`

Expected: the official PostgreSQL 18.4 image is downloaded if absent and the service becomes healthy.

- [ ] **Step 2: Apply the real migration**

Run: `uv run alembic -c src/alembic/alembic.ini upgrade head`

Expected: revision `0001_initial_schema` is applied successfully.

- [ ] **Step 3: Add the failing round-trip test**

The test must use `TEST_DATABASE_URL`, skip destructive cleanup against URLs whose hostname is not `localhost` or `127.0.0.1`, create unique synthetic records, and clean only those records in `finally`. It must assert the Phase 1 state transitions through public service/repository interfaces.

- [ ] **Step 4: Verify RED, then implement only integration defects**

Run: `TEST_DATABASE_URL=postgresql://donde_ayudo:donde_ayudo_local@localhost:5432/donde_ayudo uv run pytest tests/integration/test_postgres_round_trip.py -q`

Expected initial result: FAIL on the first real persistence mismatch, or PASS if the already implemented contract is complete. If it passes immediately, retain it as integration evidence rather than inventing a defect.

- [ ] **Step 5: Run Phase 1 verification**

```bash
uv run pytest -q
python3 .codex/hooks/project_guard.py --validate
```

Expected: all tests PASS and `project harness: PASS`.

- [ ] **Step 6: Update verified documentation**

Mark only acceptance criteria evidenced by tests and browser checks. Document that local Docker and Supabase use the same migration and application code, and differ only by `DATABASE_URL`.
