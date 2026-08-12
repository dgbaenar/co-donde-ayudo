# AGENTS.md

## Purpose

This file defines durable engineering guidance for Codex in this repository. Keep reusable harness instructions independent of application requirements; treat specifications and task documents as inputs to a particular work session.

## Project context

- Repository/project name: `co-donde-ayudo`; public brand: **Dónde Ayudo** at `dondeayudo.co`.
- Build a simple, mobile-first web app to coordinate citizen aid during emergencies in Colombia.
- The core entity is a **Punto de ayuda**: public visitors see current needs and their status, while
  its coordinator manages that single point through a private admin link.
- The MVP is one Python NiceGUI application backed by Supabase/PostgreSQL, with exactly four
  application tables: `help_points`, `need_categories`, `needs`, and `commitments`.
- Follow the four phases in [the MVP](docs/product/mvp.md#33-desarrollo-por-fases) and apply strict
  YAGNI: do not add features beyond the active phase or explicit requirement.
- Do not introduce concepts outside this product domain or the active MVP phase.

## Environment and source layout

- When a Python project is initialized, require Python `>=3.12`, declare it in `pyproject.toml`, and
  use `uv` as the only project and environment manager.
- Keep application code in separate `src/backend/` and `src/frontend/` packages.
- Organize cohesive responsibilities in subpackages: backend domain models under
  `src/backend/domain/`, use-case orchestration under `src/backend/application/`, external
  adapters/configuration under `src/backend/infrastructure/`, and UI pages under
  `src/frontend/pages/`. Keep `src/frontend/app.py` limited to route composition.
- Keep all PostgreSQL persistence in `src/backend/infrastructure/postgres/`; use SQLAlchemy ORM
  sessions and transactions with Psycopg as the PostgreSQL driver. Schema changes use Alembic
  under `src/alembic/`; do not add manual `.sql` files.
- Do not mix domain rules, persistence, configuration, and UI rendering in the same module.
- Use absolute internal imports rooted at `backend` or `frontend`; relative imports are prohibited.
- Keep tests aligned under `tests/backend/`, `tests/frontend/`, and `tests/integration/`.
- Backend code owns business rules, validation, persistence access, and external-service adapters.
  Frontend code owns presentation and user interaction, consumes an explicit backend-facing
  interface, and never accesses persistence clients directly.
- Do not let backend code import UI frameworks or create another deployment boundary without an
  approved current requirement.

## Engineering workflow

- Work on one small, dependency-ready task with explicit scope and binary acceptance criteria.
- Inspect applicable instructions and current repository evidence before changing files.
- For behavior changes, first add or identify a focused test and observe it fail for the expected
  reason. Then implement the smallest coherent solution that makes it pass.
- Avoid speculative layers, unrelated cleanup, hidden mutable global state, and import-time side
  effects. Make surgical edits and inspect their final content directly.
- Stop for a decision when repository evidence cannot resolve a material ambiguity.

## Dependencies and security

- Do not add, remove, update, or install dependencies without explicit user approval.
- Before requesting approval, report the exact version, release age, purpose, scope, lockfile
  impact, and important transitive risks.
- Never read, print, log, expose, or commit credentials, real environment-file contents, or private
  data. Use synthetic fixtures and configuration-driven secrets.
- Treat external writes, paid services, real infrastructure, and private data as explicit approval
  boundaries.

## Verification

- Derive verification from the active acceptance criteria and run the narrowest relevant checks,
  followed by broader configured checks when warranted.
- Report exact commands, current results, skipped checks, and environmental blockers.
- Never claim completion from intended changes, a subagent report, or stale output. Independently
  inspect final files and reproduce decisive checks.

## Git boundary

Read-only Git inspection is allowed. Creating or switching branches, staging, committing, pushing,
rebasing, merging, rewriting history, changing remotes, and writing pull requests require explicit
user approval. No skill or subagent can grant that approval.

## Subagent routing

- Default to fan-out on every development stage: identify independent backend, frontend,
  verification, documentation, or research workstreams and dispatch them concurrently.
- When implementation is inherently sequential, keep writes sequential but fan out read-only
  review, verification, or dependency analysis that cannot conflict with the active writer.
- The main agent owns scope, user decisions, task selection, and final integration.
- Delegate one approved backend task to `backend_developer` and one approved frontend task to
  `frontend_developer`; keep their write surfaces separate.
- Use `local_verifier` for read-only checks, `python_architect` for structural review,
  `document_reviewer` for supplied documents, and `integrity_auditor` for an independent evidence
  and scope audit.
- Fan out only work with no shared write surface or sequential dependency. Treat every subagent
  report as an evidence input that still requires direct verification.

## Detailed rules

Load the policy whose scope applies before acting:

- [Engineering](.codex/rules/engineering.md)
- [Testing](.codex/rules/testing.md)
- [Security](.codex/rules/security.md)
- [Dependencies](.codex/rules/dependencies.md)
- [Documentation](.codex/rules/documentation.md)
- [Git](.codex/rules/git.md)
- [Delegation](.codex/rules/delegation.md)
