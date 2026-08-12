# Generic Codex harness design

## Purpose

Create a complete, project-scoped Codex development harness while leaving the existing Claude
harness unchanged. The Codex harness defines how engineering work is planned, delegated,
implemented, reviewed, and verified. It does not describe what the application does.

Product requirements, domain entities, user flows, database tables, UI copy, and phase-specific
acceptance criteria are inputs to later development work and remain outside the harness.

## Success criteria

The harness is complete when:

1. Codex loads concise engineering guidance from `AGENTS.md`.
2. Repo-scoped skills are discoverable under `.agents/skills/`.
3. Custom subagents are valid TOML files under `.codex/agents/`.
4. Hooks are valid, non-destructive, and use no downloaded runtime tooling.
5. Rules cover engineering, testing, security, dependencies, documentation, Git, and delegation.
6. Frontend and backend work have separate ownership without defining application behavior.
7. No Codex-harness file contains inherited domain content or the new product description.
8. The original Claude harness is byte-for-byte unchanged.
9. All references in the harness resolve to real files.

## Harness boundary

The harness consists only of:

```text
AGENTS.md
.codex/**
.agents/skills/**
```

The design specification under `docs/superpowers/specs/` documents how the harness is built but is
not loaded as runtime project guidance. Product documentation, source code, tests, SQL, packaging,
and deployment files are explicitly outside the harness.

## Harness layout

```text
AGENTS.md

.codex/
    config.toml
    hooks.json
    hooks/
        project_guard.py
    agents/
        backend_developer.toml
        frontend_developer.toml
        local_verifier.toml
        python_architect.toml
        document_reviewer.toml
        integrity_auditor.toml
    rules/
        engineering.md
        testing.md
        security.md
        dependencies.md
        documentation.md
        git.md
        delegation.md

.agents/
    skills/
        product-development/
            SKILL.md
            METHODOLOGY.md
        backlog-execution/
            SKILL.md
            EVALUATION.md
        codebase-architecture/
            SKILL.md
        git-messages/
            SKILL.md
            template.md
            scripts/
            examples/
        session-summarizer/
            SKILL.md
            TEMPLATE.md
```

No files are copied, linked, imported, or executed from `.claude/`.

## Root instructions

`AGENTS.md` is a concise index of durable engineering rules. It contains:

- use Python `>=3.12`, `pyproject.toml`, and `uv` when a Python project is initialized;
- place application code under separate `src/backend/` and `src/frontend/` packages;
- keep tests aligned with the source ownership boundary;
- work in small, dependency-ready tasks with binary acceptance criteria;
- write a failing test before implementation for behavior changes;
- prefer the smallest coherent solution and reject speculative architecture;
- never change dependencies, Git history, external systems, or paid services without approval;
- protect secrets and private data;
- delegate implementation and independent review to the appropriate subagents;
- run and report real verification before claiming completion;
- load detailed policy files only when their scope applies.

It does not contain application purpose, feature lists, data models, UI requirements, backlog IDs,
phase descriptions, or product terminology.

## Technical source convention

The harness establishes this future code ownership convention without prescribing application
content:

```text
pyproject.toml
src/
    backend/
    frontend/
tests/
    backend/
    frontend/
    integration/
```

`src/backend/` owns business rules, validation, persistence access, and external-service adapters.
`src/frontend/` owns pages, components, presentation, and user interaction. Frontend code consumes
a small backend-facing Python interface and does not access persistence clients directly. Backend
code does not import UI frameworks. Both remain part of one Python project unless later product
requirements explicitly approve another deployment boundary.

These are engineering boundaries only. The harness does not name routes, screens, entities,
states, services, tables, or fields.

## Custom subagents

### `backend_developer`

Implements exactly one approved backend task and its tests. It is limited to the task card's paths
and acceptance criteria, cannot change frontend files or dependencies without approval, and ends
with a criterion-by-criterion evidence report.

### `frontend_developer`

Implements exactly one approved frontend task and its tests. It owns `src/frontend/**`, consumes an
existing backend contract, verifies user-visible states and a mobile viewport when applicable, and
cannot change backend code, persistence, dependencies, or global configuration without approval.

### `local_verifier`

Runs configured checks without editing files. It reports exact commands, outputs, skipped checks,
and environmental blockers. External integrations use approved test environments or local fakes;
the verifier never installs missing tools.

### `python_architect`

Reviews changed Python files for responsibility, dependency direction, testability, source-package
ownership, and unnecessary complexity. It treats over-engineering and cross-boundary shortcuts as
findings and returns one consolidated report.

### `document_reviewer`

Reviews a user-supplied specification, plan, or backlog for clarity, internal consistency, scope,
feasibility, and binary acceptance criteria. It reconciles status claims with repository evidence
but does not invent product requirements.

### `integrity_auditor`

Independently checks that claimed results are supported by reproducible evidence, critical safety
and privacy requirements are tested, scope has not expanded, and unresolved failures are reported
honestly. Its criteria come from the active task, not from embedded domain assumptions.

## Skills

### `product-development`

Accepts paths to user-supplied product documents at invocation time. It reviews those documents
from independent product and engineering perspectives, reconciles findings against the repository,
and stops for decisions that cannot be derived from evidence. The skill contains no built-in
product description or default feature set.

### `backlog-execution`

Runs a generic small-task loop:

1. inspect repository and active instructions;
2. load the backlog path supplied at invocation;
3. select one dependency-ready task;
4. present scope and binary acceptance criteria;
5. obtain required approval;
6. dispatch the appropriate implementer;
7. dispatch independent verification and review;
8. resolve every finding or report a real blocker;
9. update evidence only after final verification.

The skill never branches, commits, pushes, opens a pull request, changes dependencies, or contacts
external systems without explicit approval.

### `codebase-architecture`

Explores or updates a lean architecture map when requested or when an approved structural change
requires it. It records current packages, dependency direction, configuration, data flow, and
invariants. It does not require speculative layers, diagrams, or future components.

### `git-messages`

Produces commit and pull-request text from the actual diff. It performs no Git mutation.

### `session-summarizer`

Creates a compact, path-based handoff when explicitly requested. It records verified state,
commands actually run, blockers, and the next approved task without duplicating source documents.

## Rules

### Engineering

- Prefer the smallest implementation that satisfies the active task.
- Keep modules cohesive and names specific.
- Avoid hidden mutable global state and import-time side effects.
- Preserve the `src/backend/` and `src/frontend/` ownership boundary.
- Do not add architectural layers without a current requirement.
- Make surgical changes and inspect final content directly.

### Testing

- Test meaningful public behavior and critical invariants.
- Derive tests from acceptance criteria.
- Require a failing test before behavior implementation.
- Use local fakes for external systems by default.
- Never claim a test passed without current command output.
- Keep frontend, backend, and integration tests in their owning paths.

### Security

- Never read, print, log, expose, or commit real environment files or credentials.
- Keep secrets server-side and configuration-driven.
- Use synthetic data in tests and examples.
- Treat external writes, real infrastructure, and private data as approval boundaries.
- Report security failures explicitly; do not silently downgrade behavior.

### Dependencies

- `uv` is the exclusive Python project and environment manager.
- Before changing a dependency, state its exact version, release age, purpose, scope, lockfile
  impact, and major transitive risks.
- Require explicit approval before dependency-changing or installing commands.
- Do not use ad-hoc installers, unverified URLs, or unofficial registries.

### Documentation

- Maintain one source of truth per topic.
- Use real paths, configured commands, and verified status.
- Link instead of duplicating large documents.
- Update documentation with the behavior it describes.
- Never embed product content in harness instructions or reusable skills.

### Git

- Read-only inspection is allowed.
- Branching, committing, pushing, rebasing, merging, and pull-request writes require explicit
  approval.
- A skill or subagent cannot grant itself that approval.

### Delegation

- The main agent coordinates scope, decisions, and final integration.
- Use one specialized implementer per approved task.
- Use independent agents for verification and review.
- Fan out only work that has no shared write surface or sequential dependency.
- Subagent reports are evidence inputs, not proof; inspect final files and run checks independently.

## Hooks

The initial hook configuration uses one standard-library Python script in two modes:

1. `PreToolUse` guards write-capable shell and patch calls that target `CLAUDE.md` or `.claude/`.
2. `Stop` performs non-destructive validation of the Codex harness.

The script reads the current hook JSON schema from standard input and emits the supported Codex
decision shape. It never formats, edits, installs, downloads, contacts the network, or relies on
Git being initialized.

Stop checks:

- required harness paths exist;
- JSON and TOML parse successfully;
- every skill has valid `name` and `description` frontmatter;
- every referenced harness path exists;
- no harness file imports or links to `.claude/`;
- agent ownership paths do not overlap unexpectedly;
- no obvious credentials or environment-file contents are present.

The hook contains no domain vocabulary or product-aware deny-list. Absence of inherited or current
product content is verified once during harness construction with non-persisted scan inputs; those
inputs are not copied into the hook or any other harness file.

The hook is tested directly with passing and intentionally failing temporary fixtures before being
registered. Hook trust remains a user-controlled Codex action.

## Harness implementation sequence

1. Record a read-only digest inventory of `CLAUDE.md` and `.claude/**`.
2. Create `AGENTS.md` and `.codex/rules/**`.
3. Create all custom agents, including `frontend_developer`.
4. Create the repo-scoped skills.
5. Create and test the non-destructive hook.
6. Parse all JSON and TOML and validate skill metadata and references.
7. Run a one-time, non-persisted scan of the harness boundary for inherited and current product
   content.
8. Recompute the Claude-harness digest inventory and require an exact match.
9. Inspect the final Codex files directly.

Only after this gate passes does product development begin. The product prompt is then treated as
an external task input, not copied into or referenced by the harness.

## Phase 1 handoff

Starting Phase 1 is outside harness construction. At that point, the active product specification
may create its own documents and backlog. The first foundation task establishes `pyproject.toml`,
the supported Python range, the `uv` workflow, and empty `src/backend/` and `src/frontend/` package
boundaries before feature code is added.

The harness does not predefine the contents of Phase 1. It only supplies the workflow used to
select, approve, implement, review, and verify it.

## Non-goals

- Describing the application or copying its prompt into harness files.
- Encoding domain entities, fields, states, routes, pages, or acceptance criteria.
- Changing, deleting, linking, importing, or reformatting Claude-harness files.
- Installing dependencies or initializing the Python project during harness construction.
- Performing Git mutations during harness construction.
- Running real external-service operations as part of harness validation.
