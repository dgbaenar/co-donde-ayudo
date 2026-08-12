# Post-creation and Mobile UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the emergency context, mobile selection, private-link handoff, public point detail,
and single-point administration clear and safe without expanding the MVP data model.

**Architecture:** Keep all behavior inside the existing NiceGUI frontend boundaries. The runtime
passes the validated non-secret base URL to creation; pages render explicit responsive sections and
consume the same backend callables. Clipboard behavior is client-side and promise-aware; destructive
admin actions are guarded in page-local confirmation dialogs.

**Tech Stack:** Python 3.14 runtime compatible with project `>=3.12`, NiceGUI 3.15, Quasar QSelect,
pytest/unittest fakes, uv.

## Global Constraints

- Use absolute imports only; do not add or update dependencies.
- Do not read `.env`, print secrets, or put `admin_token` in public content, notifications, logs,
  headings, DOM identifiers, or real test fixtures.
- Keep exactly four application tables and do not modify backend domain, persistence, or Alembic.
- Preserve `/crear` authorization and per-point private administration links.
- All long menus in this plan use `behavior=menu` and
  `popup-content-style="max-height: 40vh; overflow-y: auto"`; do not use `options-dense`.
- Use TDD: observe the focused expected failure before production changes.
- Do not mutate Git: no branch, stage, commit, push, or PR operations.

---

### Task 1: Home emergency context, header, and bounded filters

**Files:**
- Modify: `src/frontend/pages/home.py`
- Test: `tests/frontend/test_home.py`

**Interfaces:**
- Consumes: existing `render_home(points, categories, list_departments, list_localities)`.
- Produces: unchanged function signature and filtering behavior.

- [ ] **Step 1: Write failing presentation tests**

Add assertions to the existing recording-UI test:

```python
labels = [e.args[0] for e in fake_ui.elements if e.kind == "label"]
self.assertEqual(labels.count("¿Dónde ayudo?"), 1)
self.assertIn("Emergencia activa", labels)
self.assertIn("Respuesta al terremoto de Chocó", labels)
self.assertIn(
    "Encuentra puntos de ayuda para zonas afectadas en Chocó, Caldas, "
    "Valle del Cauca, Risaralda y Quindío.",
    labels,
)
for select in location_selects:
    self.assertIn("behavior=menu", select.props_value)
    self.assertIn('popup-content-style="max-height: 40vh; overflow-y: auto"', select.props_value)
    self.assertNotIn("options-dense", select.props_value)
```

Record parent/child topology and require the pin icon and title to share the same header row while
the coordinator CTA remains in that row.

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```bash
uv run --no-sync pytest -q tests/frontend/test_home.py
```

Expected: failures for the missing earthquake context, title outside the icon row, and old select
props.

- [ ] **Step 3: Implement the minimal home changes**

In `render_home`:

```python
with ui.row().classes("items-center gap-2 min-w-0"):
    ui.icon("location_on").classes("text-white bg-emerald-700 rounded-xl p-2 text-xl")
    ui.label("¿Dónde ayudo?").classes(
        "text-xl sm:text-2xl font-semibold leading-tight text-emerald-950"
    )
```

Keep the CTA as the other child of the outer header. Replace the former hero title with only its
subtitle. Add a neutral `rounded-2xl bg-slate-100 p-4` context panel before filters using the exact
three approved strings. Change both home selects to:

```python
.props(
    'outlined dense behavior=menu color=blue-grey-9 '
    'popup-content-style="max-height: 40vh; overflow-y: auto"'
)
```

- [ ] **Step 4: Verify GREEN**

Run the focused test again and then:

```bash
uv run --no-sync pytest -q tests/frontend/test_home.py tests/frontend/test_help_point_map.py
```

Expected: all pass; filtering/map/list behavior is unchanged.

---

### Task 2: Post-create private-link success and mobile creation menus

**Files:**
- Modify: `src/frontend/pages/create_help_point.py`
- Modify: `src/frontend/app.py`
- Modify: `src/frontend/runtime.py`
- Test: `tests/frontend/test_create_help_point.py`
- Test: `tests/frontend/test_coordinator_access.py`
- Test: `tests/frontend/test_runtime.py`

**Interfaces:**
- Produces: `build_admin_url(app_base_url: str, admin_path: str) -> str`.
- Changes: `render_create_help_point(..., geocode_address, app_base_url: str) -> None`.
- Changes: `create_app(..., app_base_url: str, ...) -> None`; runtime passes
  `settings.app_base_url`.

- [ ] **Step 1: Write failing URL and rendering tests**

Add pure tests:

```python
self.assertEqual(
    build_admin_url("https://dondeayudo.co/base/?x=1#fragment", "/administrar/synthetic-token"),
    "https://dondeayudo.co/administrar/synthetic-token",
)
```

Extend the recording UI with visibility, enable/disable, readonly input, and async JavaScript
records. After invoking the publish callback with a synthetic token, assert:

```python
self.assertEqual(create_calls, [expected_command])
self.assertIn("Punto de ayuda publicado", labels)
self.assertIn("Este enlace es privado. Cópialo y guárdalo: lo necesitarás para administrar el punto.", labels)
self.assertEqual(url_input.value, "https://dondeayudo.co/administrar/synthetic-token")
self.assertIn("readonly", url_input.props_value)
self.assertTrue(form_container.visible is False)
```

Click `Copiar enlace` and require the browser script to receive the JSON-encoded absolute URL.
Return `True`/`False` from the fake and assert distinct generic notifications. Assert no copy runs
during rendering. Invoke publish twice synchronously and through an in-flight test double; require
only one custom-category/point call. Make a failing create handler and require re-enabled publish,
visible form, and no success URL.

Assert the four location selects and `Necesidades` use the global bounded-menu props and omit
`options-dense`.

- [ ] **Step 2: Run creation/wiring tests and observe RED**

```bash
uv run --no-sync pytest -q tests/frontend/test_create_help_point.py \
  tests/frontend/test_coordinator_access.py tests/frontend/test_runtime.py
```

Expected: failures for missing base URL, success state, guards, copy behavior, and menu props.

- [ ] **Step 3: Implement canonical URL construction**

Use `urllib.parse.urlsplit`:

```python
def build_admin_url(app_base_url: str, admin_path: str) -> str:
    parsed = urlsplit(app_base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/{admin_path.lstrip('/')}"
```

The settings boundary already validates HTTP(S) scheme and hostname. Do not read environment data
inside the page.

- [ ] **Step 4: Implement guarded form/success states**

Use separate form and success containers plus `submitting` and `published` booleans. Before custom
category or point writes, set `submitting = True` and disable the publish button. A guarded repeat
returns. On `TypeError`/`ValueError`, reset the guard and button. On success, set `published`, hide
the form, and render the success view.

The copy callback is async and calls `ui.run_javascript` with a JSON-encoded URL:

```python
script = (
    "navigator.clipboard.writeText(" + json.dumps(admin_url) + ")"
    ".then(() => true).catch(() => false)"
)
copied = bool(await ui.run_javascript(script))
```

Show the exact approved success/failure notifications without URL/token content. The readonly URL
remains visible in both outcomes.

- [ ] **Step 5: Wire base URL and bounded menus**

Pass `settings.app_base_url` through runtime and app into the protected create renderer. Apply the
global bounded-menu props to the four location selects and `Necesidades` only.

- [ ] **Step 6: Verify GREEN**

Run the focal command from Step 2 and:

```bash
uv run --no-sync pytest -q tests/frontend
```

Expected: all frontend tests pass; auth redirect and storage behavior remain unchanged.

---

### Task 3: Structured public point detail

**Files:**
- Modify: `src/frontend/pages/help_point_detail.py`
- Test: `tests/frontend/test_help_point_detail.py`

**Interfaces:**
- Consumes unchanged `PublicHelpPoint`, category mapping, and `render_help_point_map`.
- Produces unchanged public route behavior and not-found response.

- [ ] **Step 1: Write failing hierarchy tests**

Extend the fake with `row`, `grid`, `link`, and `.props`. Assert one `role=heading aria-level=1`
containing the point name, level-two headings for `Ayuda destinada a`, `Recibe ayuda en`,
`Necesidades actuales`, and `Ubicación del punto de recepción`, a `Volver al mapa` link, and a
responsive `md:grid-cols-2` location grid. Add one need in every status and assert each complete
status text plus red/amber/emerald semantic classes. Preserve the existing map-call and generic
not-found assertions.

- [ ] **Step 2: Run detail tests and observe RED**

```bash
uv run --no-sync pytest -q tests/frontend/test_help_point_detail.py
```

Expected: missing headings, sections, grid, status rows, and map heading.

- [ ] **Step 3: Implement neutral semantic sections**

Render a `bg-slate-50` page with `max-w-4xl`, a white header card, a stacked/mobile two-column
location grid, one bordered status row per need, and a map section. Use dynamic labels with:

```python
ui.label(point.name).props("role=heading aria-level=1")
ui.label("Ayuda destinada a").props("role=heading aria-level=2")
```

Do not interpolate point data into raw HTML. Keep the physical map center/zoom unchanged.

- [ ] **Step 4: Verify GREEN**

```bash
uv run --no-sync pytest -q tests/frontend/test_help_point_detail.py \
  tests/frontend/test_help_point_map.py
```

Expected: all pass.

---

### Task 4: Structured and safe single-point administration

**Files:**
- Modify: `src/frontend/pages/manage_help_point.py`
- Test: `tests/frontend/test_manage_help_point.py`

**Interfaces:**
- Preserves all existing helper and renderer signatures.
- Produces page-local confirmation dialogs; backend handlers remain unchanged.

- [ ] **Step 1: Write failing section, color, and confirmation tests**

Extend recording elements with `.props`, dialog `open/close`, and nested children. Assert headings
for `Información pública`, `Necesidades`, `Agregar necesidad`, and `Zona de peligro`; point name is
visible; save buttons contain `unelevated color=green-9`; add contains `outline color=green-9`;
remove contains `outline color=red-9`; final deactivate confirmation contains
`unelevated color=red-9`.

Click remove/deactivate launch buttons and assert zero mutation calls. Click `Cancelar` and assert
zero. Reopen and click each explicit confirmation; assert exactly one handler call with the same
point/token/need ID. Assert all visible confirmation text omits the synthetic token.

Assert both admin selects use `behavior=menu`; `Agregar necesidad` also has the global 40vh popup
style and neither uses `options-dense`. Assert status options equal the complete public copy.

- [ ] **Step 2: Run administration tests and observe RED**

```bash
uv run --no-sync pytest -q tests/frontend/test_manage_help_point.py
```

Expected: missing sections, props, dialog behavior, complete copy, and mobile select props.

- [ ] **Step 3: Implement sections and explicit action palette**

Keep `apply` as the single mutation/refresh path. Build neutral cards for information, needs, add,
and danger zone. Apply the exact green/red props and minimum 44 px classes from the spec.

Create a confirmation dialog for each need removal and one for deactivation. Launching/cancelling
never calls `apply`; only the confirmation callback closes its dialog and calls `apply` once.
Capture need IDs with default callback arguments so each dialog targets its own need.

Update `status_options()` to:

```python
{
    "Se necesita": NeedStatus.NEEDS_HELP,
    "Hay ayuda en camino — todavía se necesita": NeedStatus.HELP_ON_THE_WAY,
    "Cubierto — no enviar más": NeedStatus.COVERED,
}
```

- [ ] **Step 4: Verify GREEN**

```bash
uv run --no-sync pytest -q tests/frontend/test_manage_help_point.py
```

Expected: all delegation, rendering, palette, confirmation, and selector tests pass.

---

### Task 5: Product documentation and integrated verification

**Files:**
- Modify: `docs/product/mvp.md`
- Modify: `docs/product/backlog.md`
- Modify: `README.md` only if local phone `APP_BASE_URL` guidance is missing

**Interfaces:**
- Consumes final behavior from Tasks 1–4.
- Produces documentation without contradictory old header, flat-detail, immediate-destructive, or
  full-screen-mobile-selector statements.

- [ ] **Step 1: Update only contradictory documentation**

Document the exact earthquake-context copy, title beside pin, bounded menus, post-create success,
canonical absolute private link, public-detail sections, explicit admin palette, and destructive
confirmations. State that LAN phone testing needs `APP_BASE_URL=http://IP_DE_TU_MAC:8080` if the
copied link must work on that phone. Preserve four tables and all unrelated MVP requirements.

- [ ] **Step 2: Run complete automated verification**

```bash
uv run --no-sync pytest -q
uv lock --check
rg -n '^\s*(from\s+\.|import\s+\.)' src tests
```

Expected: all configured tests green, only the documented optional PostgreSQL integration may
skip, lock consistent, relative-import scan empty.

- [ ] **Step 3: Restart and verify browser flows**

At 1280x900, 390x844, and 375x667 verify home hierarchy/context, bounded menus, no horizontal
overflow, public detail sections, creation authorization, success/copy with only synthetic local
data, and admin palette/confirmations using the newly created private test link. Do not reveal the
coordinator key or private link in output. Confirm no browser console warnings/errors.

- [ ] **Step 4: Independent scope/security review**

Verify no table/dependency changes, no token in public/notification/log content, no duplicate
write path, destructive cancel safety, exact earthquake copy, and unchanged backend authorization.

---

### Task 6: Coordinator access guidance

**Files:**
- Modify: `src/frontend/pages/coordinator_access.py`
- Test: `tests/frontend/test_coordinator_access.py`

- [ ] **Step 1: Observe RED for the approved explanatory copy and responsive card**

Require the exact coordinator/recollection explanation, the exact plain-text WhatsApp contact
`dan.barod`, no fabricated URL, and a large primary `Continuar` action. Preserve all existing
wrong/correct-key behavior tests.

- [ ] **Step 2: Implement the minimal presentation**

Use a neutral card, exact copy from the approved design, no contact link, and
`unelevated color=green-9` with a minimum 48 px target. Do not change session or authorization.

- [ ] **Step 3: Verify**

```bash
uv run --no-sync pytest -q tests/frontend/test_coordinator_access.py
```

---

### Task 7: Railway-safe runtime and container

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `railway.toml`
- Modify: `src/backend/core/config.py`
- Modify: `src/backend/infrastructure/postgres/database.py`
- Modify: `src/frontend/runtime.py`
- Modify: `src/frontend/app.py`
- Test: `tests/backend/test_settings.py`
- Test: `tests/backend/test_database.py`
- Test: `tests/frontend/test_runtime.py`
- Test: `tests/frontend/test_coordinator_access.py`
- Modify: `README.md`

- [ ] **Step 1: Observe focused RED**

Test validated `PORT` with local default 8080, explicit host/port/show runtime arguments,
generic `/healthz` and DB-backed `/readyz`, successful/failing probes without exception details,
Docker lock installation/non-root user, and Railway pre-deploy/health/restart configuration.

- [ ] **Step 2: Implement runtime/readiness**

Add a no-side-effect PostgreSQL `SELECT 1` probe, inject it into `create_app`, expose health routes,
and bind NiceGUI to `0.0.0.0:$PORT` with `show=False`. Keep imports absolute and secrets out.

- [ ] **Step 3: Add deterministic deployment files**

Build from `uv.lock` in a root Dockerfile, exclude local/private artifacts, and configure Railway to
run Alembic once before start, check `/readyz`, and restart on failure. Do not run Alembic in CMD.

- [ ] **Step 4: Document release protection**

Document required variables and exact build/predeploy/start/health behavior, provider backup and
restore verification, write freeze for existing migration 0002, app rollback vs database rollback,
forward-fix preference, and expand/backfill/deploy/contract for future migrations.

- [ ] **Step 5: Verify focused and full checks**

```bash
uv run --no-sync pytest -q tests/backend/test_settings.py tests/backend/test_database.py \
  tests/frontend/test_runtime.py tests/frontend/test_coordinator_access.py
uv run --no-sync pytest -q
uv lock --check
```
