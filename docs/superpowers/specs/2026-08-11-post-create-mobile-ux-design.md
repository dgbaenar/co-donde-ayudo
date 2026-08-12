# Post-creation and mobile-selection UX design

**Date:** 2026-08-11  
**Status:** Approved in conversation; pending written-spec review  
**Scope:** NiceGUI frontend only, plus composition wiring for the public base URL

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

### Mobile select menus

Exactly these six location selectors use QSelect `behavior=menu` instead of the mobile full-screen
dialog: home `Departamento` and `Ciudad / Municipio`; creation `Departamento afectado`,
`Ciudad / Municipio afectado`, `Departamento del punto`, and `Ciudad / Municipio del punto`.
Their popup content uses `max-height: 50vh; overflow-y: auto` and remains scrollable. Remove
`options-dense`: normal option height is easier to tap. Do not introduce global CSS, persistent
menus, or `options-cover`.

The creation multi-select `Necesidades` is the seventh selector in scope and receives the same menu
behavior and height cap because it can also be a long list. Single-value menus close after a
selection. The needs menu may remain open while several needs are chosen and closes when the
coordinator taps outside; its 50vh cap keeps the surrounding form visible. Dependent municipality
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

## Code boundaries

- `src/frontend/pages/create_help_point.py`: form/success states, duplicate-submit guard, copy UI.
- `src/frontend/pages/home.py`: compact header and bounded filter selects.
- `src/frontend/app.py`: pass the validated public base URL to the creation route.
- `src/frontend/runtime.py`: supply `ApplicationSettings.app_base_url` without exposing secrets.
- Frontend tests only; no backend, schema, dependency, or authentication changes.

## Acceptance criteria

- Pin and `¿Dónde ayudo?` share one header container; the title appears once.
- Every long mobile selector uses a scrollable `behavior=menu` popup capped at `50vh`; location
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
- Frontend tests and the full configured suite pass; browser checks cover 1280x900, 390x844, and
  375x667 with no horizontal overflow or console errors.

## Out of scope

- Coordinator accounts, link recovery, email/SMS delivery, QR codes, sharing APIs, analytics, or
  another persistence table.
- Redesigning administration or public point detail pages.
- Adding a clipboard, select, or responsive-layout dependency.
