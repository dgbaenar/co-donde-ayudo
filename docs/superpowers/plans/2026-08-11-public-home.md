# Public Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the basic public home with the approved map-first, compact-list experience while preserving the existing public data and routes.

**Architecture:** Keep filtering and page composition in `frontend.pages.home`; keep Leaflet marker and popup rendering in `frontend.components.help_point_map`. Derive filter choices from active points already returned by the backend, and render map, count, and list from one filtered tuple.

**Tech Stack:** Python 3.12+, NiceGUI 3.15, Leaflet through NiceGUI, pytest, uv.

## Global Constraints

- Use absolute imports rooted at `backend` or `frontend`.
- Do not add dependencies, tables, backend behavior, geolocation, search, distances, routes, category filters, or GIS features.
- Do not use Playwright or a browser for verification.
- Do not read `.env` or mutate Git.
- Preserve `/`, `/acceso`, `/crear`, `/puntos/{point_id}`, and private administration behavior.
- Mobile: stacked map then list. Desktop: main map column plus compact list column.

---

### Task 1: Reactive location filters and synchronized results

**Files:**
- Modify: `src/frontend/pages/home.py`
- Test: `tests/frontend/test_home.py`

**Interfaces:**
- Consumes: `Sequence[PublicHelpPoint]`, `Mapping[str, UUID]`, and `render_help_point_map(points, categories)`.
- Produces: `filter_public_help_points(...)`, `location_filter_options(...)`, and `render_home(...)` with reactive location controls.

- [ ] **Step 1: Write failing behavior tests**

Add tests proving these literal outcomes:

```python
assert location_filter_options(points) == (
    ("Antioquia", "Valle del Cauca"),
    ("Cali", "Medellín"),
)
assert location_filter_options(points, department="Valle del Cauca")[1] == ("Cali",)
```

Extend the recording select so its `on_change` callback can be invoked. Assert that:

```python
department.value = "Valle del Cauca"
department.on_change()
assert city.options == {"": "Todas las ciudades", "Cali": "Cali"}
assert city.value == ""
assert last_map_points == (cali_point,)
```

Also assert there is no button labeled `Aplicar filtros`, the defaults communicate all locations,
the visible result count is rendered, and the CTA is `Coordinar un punto` targeting `/acceso`.
After consecutive department and city changes, compare the IDs in public-detail link targets with
the IDs passed to the map and the literal result count. Include a zero-result event.

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```bash
uv run --no-sync pytest -q tests/frontend/test_home.py
```

Expected: failure because `location_filter_options` and reactive control behavior do not exist and the old CTA/button remain.

- [ ] **Step 3: Implement the smallest reactive filtering behavior**

Add:

```python
def location_filter_options(
    points: Sequence[PublicHelpPoint],
    *,
    department: str = "",
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    active_points = filter_public_help_points(points)
    departments = tuple(sorted({point.department for point in active_points}))
    cities = tuple(sorted({
        point.city
        for point in active_points
        if not department or point.department == department
    }))
    return departments, cities
```

Use dictionary options with the empty-string value rendered explicitly as
`Todos los departamentos` and `Todas las ciudades`; do not leave blank selects. Show the labels
`Departamento`, `Ciudad`, and the helper text `Filtrar puntos por ubicación`. Department change
must replace `city.options`, reset an incompatible city to the empty-string option, call
`city.update()`, and refresh results. City change must refresh results. Remove `Aplicar filtros`.

- [ ] **Step 4: Render the approved polished layout**

Use one page background and one bounded content column. Render:

```text
Dónde Ayudo                         Coordinar un punto
¿Dónde necesitan ayuda?
Explora el mapa o revisa la lista de puntos activos.
Filtrar puntos por ubicación
[Todos los departamentos] [Todas las ciudades]
[mapa] | [Puntos que necesitan ayuda — N resultados + lista]
```

The outer content uses `max-w-7xl`. The results use one column by default and a `3fr / 2fr` grid
from `lg`. Use a compact bordered surface for each result. Sort needs by status priority
`NEEDS_HELP`, `HELP_ON_THE_WAY`, `COVERED`, then by category name; show the first three and
`+N necesidades` for the remainder. The link targeting `/puntos/{point.id}` must wrap all visible
row content. Use status text, not color alone.

Render exact empty messages:

```text
Todavía no hay puntos de ayuda activos.
No encontramos puntos en esta ubicación. Prueba con otro departamento o ciudad.
```

The first applies when the original active tuple is empty. The second applies when active points
exist but the selected filters return none. Add one test for each state.

- [ ] **Step 5: Run focused frontend tests**

```bash
uv run --no-sync pytest -q tests/frontend/test_home.py tests/frontend/test_help_point_map.py
```

Expected: all pass.

### Task 2: Reconcile the public-home phase documentation

**Files:**
- Modify: `docs/product/mvp.md`
- Modify: `docs/product/backlog.md`

**Interfaces:**
- Consumes: approved design in `docs/superpowers/specs/2026-08-11-public-home-design.md`.
- Produces: one unambiguous phase assignment for the existing public map and the remaining location picker work.

- [ ] **Step 1: Make the phase language consistent**

Keep the public map, compact list, city/department filters, and public detail in F1-05. Change the
later Phase 3 wording so it covers the coordinator's map-based location selection and no longer
claims the public map is still absent.

- [ ] **Step 2: Mark only verified F1-05 criteria complete**

Mark criteria complete only when the final implementation and tests show active-only map/list,
location-only filters, needs inside points, no administrative data, and responsive presentation.

- [ ] **Step 3: Review documentation for contradictions**

Search `docs/product/mvp.md` and `docs/product/backlog.md` for `Fase 3`, `mapa público`,
`Lista / Mapa`, and `F1-05`; confirm no statement defers the public map after requiring it in F1.

### Task 3: Full verification and independent review

**Files:**
- Inspect all files changed by Tasks 1 and 2.

- [ ] **Step 1: Run the complete automated suite**

```bash
uv run --no-sync pytest -q
```

Expected: zero failures; report any configured integration skip exactly.

- [ ] **Step 2: Run structural checks**

```bash
uv lock --check
rg -n 'from \.|import \.' src/frontend/pages/home.py
```

Expected: lockfile current and no relative imports.

- [ ] **Step 3: Perform read-only independent review**

Verify the design requirements line by line, confirm no backend/dependency/Git scope expansion,
and report actionable findings before completion.
