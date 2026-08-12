# Post-creation and mobile-selection UX design

**Date:** 2026-08-11  
**Status:** Approved in conversation  
**Scope:** NiceGUI home, creation, public detail and single-point administration, plus composition
wiring for the public base URL

## Problem

After publishing a help point, the coordinator currently sees only an instruction and a relative
administration link below the still-active form. The link is easy to miss, a second submission can
create another point, and leaving or reloading the page loses the only copy of the private link.

On phones, NiceGUI's underlying QSelect uses its default mobile dialog behavior. Long department,
municipality, and need lists therefore cover the screen and interrupt the form flow. The public
home also renders the title below the green location pin instead of beside it.

## Approaches considered

1. **Replace the form with a focused success screen — selected.** This makes the private link the
   only task after publication and prevents accidental resubmission.
2. Keep the form and add a success card below it. This is smaller but preserves the current risks:
   the link remains easy to miss and the form can be submitted again.
3. Persist recoverable coordinator links in another account or database flow. This exceeds the
   approved MVP, weakens the four-table constraint, and creates a new authentication problem.

## Approved experience

### Public header

The green location pin and the exact title `¿Dónde ayudo?` share the left side of one responsive
header row. The `Coordinar un punto` action stays on the right. The subtitle remains below the
header. The title appears exactly once and must remain readable without horizontal overflow at
375 px.

Immediately below the header, show a compact neutral emergency-context panel:

- eyebrow: `Emergencia activa`;
- title: `Respuesta al terremoto de Chocó`;
- explanation: `Encuentra puntos de ayuda para zonas afectadas en Chocó, Caldas, Valle del Cauca,
  Risaralda y Quindío.`

This context appears before the filters and map. It does not create an event model, date selector,
news feed, or fifth table.

### Mobile select menus

Exactly these six location selectors use QSelect `behavior=menu` instead of the mobile full-screen
dialog: home `Departamento` and `Ciudad / Municipio`; creation `Departamento afectado`,
`Ciudad / Municipio afectado`, `Departamento del punto`, and `Ciudad / Municipio del punto`.
Their popup content uses `max-height: 40vh; overflow-y: auto` and remains scrollable. Remove
`options-dense`: normal option height is easier to tap. Do not introduce global CSS, persistent
menus, or `options-cover`.

The creation multi-select `Necesidades` is the seventh selector in scope and receives the same menu
behavior and height cap because it can also be a long list. Single-value menus close after a
selection. The needs menu may remain open while several needs are chosen and closes when the
coordinator taps outside; its 40vh cap keeps the surrounding form visible. Dependent municipality
enable/reset behavior remains unchanged. Administration-page selects are outside this change.

### Successful publication

The creation page has two mutually exclusive states:

- **Form state:** the existing protected form and publish action.
- **Success state:** rendered only after the backend has created the point successfully.

After the first successful publication:

1. Before any custom-category or point write, set an in-flight guard and disable the publish
   button. Any additional click while the write is in flight returns without calling a handler.
2. On failure, clear the in-flight guard, re-enable publication, keep the form visible, and render
   no private link.
3. On success, mark the page as published; subsequent publication attempts remain blocked.
4. Replace the form with a focused success screen.
5. Explain: `Punto de ayuda publicado` and
   `Este enlace es privado. Cópialo y guárdalo: lo necesitarás para administrar el punto.`
6. Show the absolute administration URL in a readonly, selectable field.
7. Show a primary `Copiar enlace` button and a secondary `Abrir administración` action.
8. The copy button executes a promise-returning browser clipboard operation. Only a resolved
   success shows `Enlace privado copiado.`. A rejection or unavailable clipboard shows
   `No se pudo copiar automáticamente. Mantén presionado el enlace y cópialo manualmente.`
   without including the URL or token in the notification.
9. The visible readonly URL is always the manual-copy fallback. Production is expected to use
   HTTPS; remote HTTP phone sessions may reject automatic clipboard access.

The success state is intentionally not persisted across reloads: no new session data, table, or
recovery framework is introduced. The warning makes saving the link an explicit final step.

### URL construction and security

The UI must copy a usable absolute URL, not `/administrar/...`. Construct it deterministically from
the origin of the configured `APP_BASE_URL`: parse the URL, keep only its validated scheme and
network location, discard any path/query/fragment, and append the private `/administrar/...` path.
This also handles multiple trailing slashes without malformed output. Pass the non-secret base URL
explicitly from `frontend.runtime` through `frontend.app` to the creation page. The local phone
environment must set `APP_BASE_URL` to the Mac LAN URL if the copied link must work from that phone;
production uses `https://dondeayudo.co` or its deployed canonical origin.

The private token may appear only in the authorized success page's readonly URL and management
link, as it already appears in the private link. It must not appear in logs, errors, generic
notifications, public pages, or tests as a real credential. Tests use synthetic tokens and URLs.

If creation fails, remain in the form state, allow correction and retry, and render no stale
success link. Authorization is still checked immediately before the backend write.

### Public point detail

Replace the current flat column with a responsive page that has a white/slate neutral hierarchy:

1. A back link `Volver al mapa`.
2. One semantic level-one heading containing the point name and a separate description.
3. A responsive two-column grid, stacked on mobile, with sections headed `Ayuda destinada a` and
   `Recibe ayuda en`.
4. A `Necesidades actuales` section with one row per need. Each row retains the complete textual
   status and uses red, amber, or emerald only as a secondary status cue.
5. An `Ubicación del punto de recepción` section containing the physical-coordinate map.

Use `role=heading` with correct `aria-level` on dynamic NiceGUI labels rather than interpolating
untrusted point content into raw HTML. Cards use subtle `border-slate-200`, white or slate surfaces,
and no oversized shadow or decorative color block.

### Single-point administration

Organize the private page into `Información pública`, `Necesidades`, `Agregar necesidad`, and
`Zona de peligro`. Show the point name below the page title. Preserve the existing operations and
token checks; this is a presentation and accidental-action-safety change, not a new permission
model.

Action palette:

- `Guardar información` and `Guardar estado`: filled `green-9`;
- `Agregar necesidad`: outlined `green-9`;
- `Quitar`: outlined `red-9`;
- `Desactivar punto`: filled `red-9` only inside `Zona de peligro`.

Every action keeps explicit text and a minimum 44 px touch target. Red is reserved for destructive
actions; the interface never relies on color alone.

`Quitar` and `Desactivar punto` open confirmation dialogs. Cancel performs no backend call.
Confirmation performs exactly one call. Dialogs and notifications must not display the
`admin_token`. The status selector uses the same complete public status text, including
`— todavía se necesita` and `— no enviar más`.

The admin `Estado` and `Agregar necesidad` selects use `behavior=menu`; the long category menu is
capped at `40vh` with scrolling and normal-height options.

## Code boundaries

- `src/frontend/pages/create_help_point.py`: form/success states, duplicate-submit guard, copy UI.
- `src/frontend/pages/home.py`: compact header and bounded filter selects.
- `src/frontend/pages/help_point_detail.py`: semantic public-detail sections and status rows.
- `src/frontend/pages/manage_help_point.py`: administrative sections, action palette, and
  destructive confirmations.
- `src/frontend/app.py`: pass the validated public base URL to the creation route.
- `src/frontend/runtime.py`: supply `ApplicationSettings.app_base_url` without exposing secrets.
- Frontend tests only; no backend, schema, dependency, or authentication changes.

## Acceptance criteria

- Pin and `¿Dónde ayudo?` share one header container; the title appears once.
- The emergency panel appears before filters with the exact approved earthquake context and five
  departments.
- Every long mobile selector uses a scrollable `behavior=menu` popup capped at `40vh`; location
  options are not dense.
- A successful create replaces the form with the private-link success screen.
- The visible and copied values are the same absolute administration URL.
- Copy occurs only after the coordinator presses `Copiar enlace`.
- A successful copy and a failed/unavailable clipboard produce different generic notifications;
  neither contains the URL or token.
- Rapid repeated publish clicks while a write is in flight and all attempts after success perform
  no additional backend or custom-category write.
- Any failed write re-enables the form and never renders a private link.
- `/crear` authorization, `admin_token` isolation, and public routes remain unchanged.
- Public detail has one level-one heading and ordered level-two sections for destination,
  reception, needs, and map; dynamic text is not inserted as raw HTML.
- Administration has the four named sections, complete status copy, and the approved green/red
  action palette.
- Cancelling destructive confirmations invokes no handler; confirming invokes exactly one.
- Admin selectors use bounded mobile menus and the private token never enters visible copy,
  notifications, logs, or DOM identifiers.
- Frontend tests and the full configured suite pass; browser checks cover 1280x900, 390x844, and
  375x667 with no horizontal overflow or console errors.

## Out of scope

- Coordinator accounts, link recovery, email/SMS delivery, QR codes, sharing APIs, analytics, or
  another persistence table.
- Adding a clipboard, select, or responsive-layout dependency.
