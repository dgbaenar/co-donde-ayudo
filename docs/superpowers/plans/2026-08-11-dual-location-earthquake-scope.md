# Dual Location and Earthquake Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distinguish the affected destination from the physical aid point, add address search with manual map fallback, scope the public filters to five departments, and simplify the visual design.

**Architecture:** Existing `city`, `department`, `latitude`, and `longitude` remain the physical aid-point location. Three columns on `help_points` carry public address and affected destination; a backend Nominatim adapter is injected into the NiceGUI creation page. Public filters operate on the affected destination while map markers remain at the physical location.

**Tech Stack:** Python 3.12+, NiceGUI 3.15.0, SQLAlchemy 2.0.51, Alembic 1.18.5, Psycopg 3.3.4, PostgreSQL, pytest 9.1.1, uv.

## Global Constraints

- Keep exactly four application tables: `help_points`, `need_categories`, `needs`, and `commitments`.
- Use absolute imports rooted at `backend` or `frontend`; relative imports are prohibited.
- Add no dependency and make no lockfile change.
- Never read `.env`, expose secrets, call real Nominatim in tests, or log address queries.
- Do not mutate Git: no branch, stage, commit, push, rebase, merge, or worktree operation.
- Affected departments are exactly `Caldas`, `Chocó`, `Quindío`, `Risaralda`, and `Valle del Cauca`.
- Physical point selectors retain all 33 Colombian departments.
- Title copy is exactly `¿Dónde ayudo?`; `¿Dónde necesitan ayuda?` must not render.
- Nominatim is explicit-button search only, at most one request per second per process, with manual map fallback.
- New global categories are exactly `Remoción de escombros` and `Maquinaria pesada`, both in group `Apoyo`.
- Preserve coordinator session protection and per-point `admin_token` behavior.

---

### Task 1: Backend location model, scope, persistence, and migration

**Files:**
- Create: `src/backend/domain/emergency_scope.py`
- Create: `src/alembic/versions/0002_help_point_locations.py`
- Modify: `src/backend/domain/models.py`
- Modify: `src/backend/application/services.py`
- Modify: `src/backend/infrastructure/postgres/orm_models.py`
- Modify: `src/backend/infrastructure/postgres/repository.py`
- Modify: `tests/backend/test_services.py`
- Modify: `tests/backend/test_repository.py`
- Modify: `tests/backend/test_migrations.py`
- Modify: `tests/integration/test_postgres_round_trip.py`

**Interfaces:**
- Produces: `AFFECTED_DEPARTMENTS: tuple[str, ...]` and `list_affected_departments() -> tuple[str, ...]` from `backend.domain.emergency_scope`.
- Produces: `CreateHelpPoint.address: str`, `affected_city: str`, and `affected_department: str`.
- Produces: `HelpPoint.address: str | None`, `affected_city: str`, `affected_department: str`; `PublicHelpPoint` exposes the same public fields.
- Changes: `HelpPointService(repository, location_catalog)` where the catalog supplies `list_localities(department: str) -> tuple[str, ...]`.
- Migration revision: `0002_help_point_locations`, down revision `0001_initial_schema`.

- [ ] **Step 1: Add failing domain and service tests**

Add tests showing that a new command carries a non-empty address and affected destination, the service rejects an affected department outside `AFFECTED_DEPARTMENTS`, rejects a municipality outside the selected department, and creates a point with all three fields.

```python
def test_create_rejects_destination_outside_active_scope(service, command):
    invalid = replace(command, affected_department="Antioquia", affected_city="Medellín")
    with pytest.raises(ValueError, match="affected department"):
        service.create_help_point(invalid)


def test_create_keeps_physical_and_affected_locations_separate(service, command):
    created = service.create_help_point(command).point
    assert (created.city, created.department) == ("Cali", "Valle del Cauca")
    assert created.address == "Calle 5 # 10-20"
    assert (created.affected_city, created.affected_department) == (
        "Roldanillo",
        "Valle del Cauca",
    )
```

- [ ] **Step 2: Run the focused backend tests and observe RED**

Run:

```bash
uv run --no-sync pytest -q tests/backend/test_services.py tests/backend/test_repository.py
```

Expected: failures because the fields, scope, catalog-aware service, and ORM mapping do not exist.

- [ ] **Step 3: Implement the domain scope and fields**

Create the immutable scope:

```python
AFFECTED_DEPARTMENTS = (
    "Caldas",
    "Chocó",
    "Quindío",
    "Risaralda",
    "Valle del Cauca",
)


def list_affected_departments() -> tuple[str, ...]:
    return AFFECTED_DEPARTMENTS
```

Add the approved fields and reuse `validate_required` with maxima 240, 120, and 120. In `HelpPointService.create_help_point`, validate that `affected_department` is in the scope and that both physical and affected municipalities appear in `location_catalog.list_localities(their_department)` before constructing the point.

- [ ] **Step 4: Add failing migration and repository tests**

Assert revision order, exactly three new columns on `help_points`, affected-location backfill, `NOT NULL` final state for affected fields, nullable legacy address, two deterministic category inserts, and no `op.create_table`. Extend repository round-trip assertions to include all three fields.

- [ ] **Step 5: Run migration/repository tests and observe RED**

Run:

```bash
uv run --no-sync pytest -q tests/backend/test_migrations.py tests/backend/test_repository.py tests/integration/test_postgres_round_trip.py
```

Expected: failures because revision `0002` and the ORM columns are absent.

- [ ] **Step 6: Implement migration and PostgreSQL mapping**

The migration must:

```python
op.add_column("help_points", sa.Column("direccion", sa.String(240), nullable=True))
op.add_column("help_points", sa.Column("ciudad_afectada", sa.String(120), nullable=True))
op.add_column("help_points", sa.Column("departamento_afectado", sa.String(120), nullable=True))
op.execute(sa.text("UPDATE help_points SET ciudad_afectada = ciudad, departamento_afectado = departamento"))
op.alter_column("help_points", "ciudad_afectada", nullable=False)
op.alter_column("help_points", "departamento_afectado", nullable=False)
```

Add named length constraints, insert category UUIDs generated with the existing
`uuid5(NAMESPACE_URL, f"donde-ayudo/category/{name}")` convention, and make downgrade delete only those two UUIDs before dropping constraints and columns. Map `direccion`, `ciudad_afectada`, and `departamento_afectado` through ORM and repository conversion.

- [ ] **Step 7: Run backend verification**

Run:

```bash
uv run --no-sync pytest -q tests/backend tests/integration/test_postgres_round_trip.py
```

Expected: backend green; the integration test may skip only when `TEST_DATABASE_URL` is absent.

---

### Task 2: Nominatim geocoding adapter

**Files:**
- Create: `src/backend/infrastructure/geocoding/__init__.py`
- Create: `src/backend/infrastructure/geocoding/nominatim.py`
- Create: `tests/backend/test_nominatim_geocoder.py`

**Interfaces:**
- Produces: `GeocodedLocation(latitude: float, longitude: float)`.
- Produces: `NominatimGeocoder.search(address: str, city: str, department: str) -> Awaitable[GeocodedLocation | None]`.
- Constructor accepts injectable request, clock, and sleep collaborators for synthetic tests; defaults use standard-library `urllib`, `time.monotonic`, and `asyncio.sleep`.

- [ ] **Step 1: Write failing adapter tests**

Cover a Colombian query with `limit=1`, `countrycodes=co`, identifying `User-Agent`, successful coordinates, empty results, invalid payload, request failure, and two concurrent/sequential calls separated to at least one second by the injected clock/sleep.

```python
def test_search_limits_query_to_colombia_and_identifies_application():
    request = RecordingRequest('[{"lat":"3.4372","lon":"-76.5225"}]')
    result = asyncio.run(geocoder(request=request).search(
        "Calle 5 # 10-20", "Cali", "Valle del Cauca"
    ))
    assert result == GeocodedLocation(latitude=3.4372, longitude=-76.5225)
    assert "countrycodes=co" in request.url
    assert "limit=1" in request.url
    assert request.headers["User-agent"].startswith("DondeAyudo/")
```

- [ ] **Step 2: Run adapter tests and observe RED**

Run:

```bash
uv run --no-sync pytest -q tests/backend/test_nominatim_geocoder.py
```

Expected: collection failure because the package does not exist.

- [ ] **Step 3: Implement the minimal async adapter**

Use `urllib.parse.urlencode`, `urllib.request.Request`, and `asyncio.to_thread`. An instance-level `asyncio.Lock` protects `_last_request_at`; before a request, await the remaining portion of one second. Use endpoint `https://nominatim.openstreetmap.org/search`, `format=jsonv2`, `limit=1`, `countrycodes=co`, and `accept-language=es`. Return `None` for no match or provider/parse/coordinate failure without logging the query.

- [ ] **Step 4: Run adapter and backend tests**

Run:

```bash
uv run --no-sync pytest -q tests/backend/test_nominatim_geocoder.py tests/backend
```

Expected: all tests green.

---

### Task 3: Frontend dual-location creation, public display, and visual cleanup

**Files:**
- Modify: `src/frontend/components/location_picker.py`
- Modify: `src/frontend/components/help_point_map.py`
- Modify: `src/frontend/pages/create_help_point.py`
- Modify: `src/frontend/pages/home.py`
- Modify: `src/frontend/pages/help_point_detail.py`
- Modify: `src/frontend/app.py`
- Modify: `src/frontend/runtime.py`
- Modify: `tests/frontend/test_location_picker.py`
- Modify: `tests/frontend/test_help_point_map.py`
- Modify: `tests/frontend/test_create_help_point.py`
- Modify: `tests/frontend/test_home.py`
- Modify: `tests/frontend/test_help_point_detail.py`
- Modify: `tests/frontend/test_runtime.py`
- Modify: `tests/frontend/test_coordinator_access.py`

**Interfaces:**
- Consumes: `list_affected_departments`, full catalog `list_departments/list_localities`, `NominatimGeocoder.search`, and the new public fields from Tasks 1–2.
- Produces: a location-picker method `set_coordinates(latitude: float, longitude: float) -> None` that updates state, marker, and map center.
- `create_app` injects both department sources and `geocode_address` separately.

- [ ] **Step 1: Write failing visual and filtering tests**

Assert exact title `¿Dónde ayudo?`, absence of `¿Dónde necesitan ayuda?`, white root, slate filter panel without `bg-emerald-50`, public affected-department options exactly equal the five-item tuple, and filtering on `affected_city/affected_department` while marker coordinates remain physical.

```python
def test_filter_uses_destination_but_map_keeps_pickup_coordinates():
    point = public_point(
        city="Cali",
        department="Valle del Cauca",
        affected_city="Roldanillo",
        affected_department="Valle del Cauca",
    )
    assert filter_public_help_points((point,), city="Roldanillo") == (point,)
    assert (point.latitude, point.longitude) == (3.4516, -76.5320)
```

- [ ] **Step 2: Write failing creation and picker tests**

Assert two independent dependent-selector pairs; affected departments are five while physical departments are 33; address is required in `FormValues`; successful geocoding calls `set_coordinates`; no result/error shows the exact fallback message and leaves address unchanged; manual map clicks still move the single marker.

- [ ] **Step 3: Run frontend focal tests and observe RED**

Run:

```bash
uv run --no-sync pytest -q tests/frontend/test_home.py tests/frontend/test_create_help_point.py tests/frontend/test_location_picker.py tests/frontend/test_help_point_map.py tests/frontend/test_help_point_detail.py
```

Expected: failures from absent fields, old filtering, old copy/styles, one selector pair, and no programmatic marker API.

- [ ] **Step 4: Implement the location picker and creation flow**

Keep one physical marker. `set_coordinates` validates ranges, updates stored coordinates, creates or moves the marker, and calls Leaflet `setView` at a useful local zoom. The create page renders:

```text
Zona que recibirá la ayuda
  Departamento afectado
  Ciudad / Municipio afectado

Dónde se recibe o coordina la ayuda
  Departamento del punto
  Ciudad / Municipio del punto
  Dirección o referencia del lugar
  Buscar en el mapa
  [mapa editable]
```

The search handler is async, validates the three physical text inputs, awaits the injected geocoder, and displays `No encontramos esa dirección. Ubícala tocando el mapa.` for `None` or provider failure. It never clears the address.

- [ ] **Step 5: Implement public filtering, display, and neutral styling**

Filter against affected fields. Display both locations in list rows, safe popup HTML, and detail. Use a white root, `bg-slate-100` filter surface without green border, white outlined selectors with `color=blue-grey-9`, slate card borders, and green only for brand/action/state accents. Render only the exact title `¿Dónde ayudo?` plus the existing concise subtitle.

- [ ] **Step 6: Wire runtime and route composition**

Instantiate `ColombiaLocationCatalog` and `NominatimGeocoder` once in `build_runtime`. Pass the catalog into `HelpPointService`, full and affected department callables into `create_app`, and `geocoder.search` only to the protected create page. Preserve `ui.run` security arguments unchanged.

- [ ] **Step 7: Run frontend verification**

Run:

```bash
uv run --no-sync pytest -q tests/frontend
```

Expected: all frontend tests green.

---

### Task 4: Product documentation and end-to-end verification

**Files:**
- Modify: `docs/product/mvp.md`
- Modify: `docs/product/backlog.md`
- Modify: `README.md`

**Interfaces:**
- Consumes final behavior from Tasks 1–3.
- Produces documentation with no contradictory single-location, all-department-filter, old-title, or no-geocoding statements.

- [ ] **Step 1: Update only contradictory product documentation**

Document the three new `help_points` fields, affected-vs-physical semantics, five-department affected filter, address search plus manual fallback, exact title, neutral visual surface, and the two debris categories. Remove `No usar geocoding inicialmente` and preserve all unrelated MVP constraints.

- [ ] **Step 2: Add mobile verification instructions**

README must include:

```bash
uv run donde-ayudo
ifconfig en0 | rg 'inet '
```

Then instruct a phone on the same Wi-Fi to open `http://IP_DE_TU_MAC:8080`; mention allowing incoming connections if macOS prompts.

- [ ] **Step 3: Run complete automated verification**

Run:

```bash
uv run --no-sync pytest -q
uv lock --check
rg -n '^\s*(from\s+\.|import\s+\.)' src tests
```

Expected: all configured tests green, only the documented optional PostgreSQL integration may skip, lock consistent, and relative-import scan empty.

- [ ] **Step 4: Run browser verification against the restarted local server**

At 1280×900, 390×844, and 375×667 verify:

- one white page background with no contrasting frame;
- neutral filter panel and exact title;
- no horizontal scroll or overlap;
- public department list contains exactly five items plus its sentinel;
- dependent municipality selector enables and resets correctly;
- map precedes list on mobile and uses physical marker coordinates;
- direct `/crear` redirects to `/acceso` without a session;
- no browser console warning/error.

Do not enter or inspect a real coordinator key. Creation behavior remains covered with synthetic tests.

- [ ] **Step 5: Independent scope and security review**

Review final files for exactly four tables, no public `admin_token`, no secret/address logging, no runtime network call before an explicit search, no dependency changes, and no features outside the approved design.
