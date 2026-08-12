---
name: codebase-architecture
description: Use when inspecting repository structure, dependency direction, data flow, configuration, or an approved structural change.
---

# Codebase architecture

Base every architectural claim on current repository evidence.

1. Read repository guidance and define the exact question or approved change.
2. Inspect relevant manifests, source roots, entry points, imports, configuration, tests, and deployment files.
3. Classify findings as `current`, `approved convention`, `proposed`, or `absent`.
4. Trace only observable dependency and data flow; cite paths for claims.
5. Identify ownership violations, cycles, hidden coupling, configuration side effects, and testability constraints.
6. Recommend the smallest change justified by the active task. Apply YAGNI.
7. Write or update architecture documentation only when requested or required by an approved structural change.

An empty directory, a plan, or a naming convention is not implemented architecture. Do not invent services, layers, integrations, diagrams, or scaling requirements. If code does not yet exist, report that plainly and describe only approved source ownership conventions.
