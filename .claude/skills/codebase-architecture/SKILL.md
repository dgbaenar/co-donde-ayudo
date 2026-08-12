---
name: codebase-architecture
description: Use when you need to understand a project's structure, key directories, module responsibilities, naming conventions, inter-component relationships, data flow, or concurrency patterns — before implementing features, refactoring, adding tests, or answering structural questions. Also use before making architectural changes to know what to update afterward.
---

# Codebase Architecture

## Pattern

Each project maintains its architecture documentation under `docs/architecture/`. Use the latest dated file in that directory as the authoritative reference. Read it before any structural work. Update it or create a new dated file after any architectural change.

## Reading

When you need architectural context, read the latest dated file in `docs/architecture/`. If none exists, create one (see below).

A well-maintained architecture document covers:

- Package/directory layout and what lives where
- Dependency graph (which modules import which; cycles are a red flag)
- Key classes, dataclasses, and type aliases with their responsibilities
- Configuration system (how settings flow from env to components)
- Data flow from system boundaries inward (I/O → domain → output)
- Concurrency model (threads, async tasks, queues, synchronization primitives)
- Key invariants and hard rules (type constraints, no global state, etc.)
- Naming conventions (module names, class names, test names, env vars)
- Current development direction and unbuilt responsibilities

## Creating (when no architecture document exists)

Explore the codebase first, then write the file. Keep it dense and precise — it is read by Claude, not humans. Avoid prose padding.

Required sections:
1. **Purpose** — one paragraph on what the system does and what it does not yet do
2. **Package layout** — annotated directory tree, one line per entry
3. **Dependency graph** — who imports who; circular imports are a runtime error, not a code smell — flag them as blockers
4. **Key components** — class names, constructor signatures, public method signatures, state fields
5. **Data flow** — end-to-end path from external input to output
6. **Concurrency model** — if async/threaded: tasks, queues, events, locks
7. **Key invariants** — rules the codebase enforces (e.g., no floats for money, no global state)
8. **Naming conventions** — module, class, function, test, env var patterns

## Updating

Update the architecture document whenever you:

- Add or remove a module or package
- Add a class, dataclass, or type alias that crosses module boundaries
- Change the dependency graph
- Change the configuration surface (new fields, new env vars)
- Change the data flow or concurrency model
- Implement or remove a system responsibility

Make the update in the same commit as the code change. Do not let the document drift.
