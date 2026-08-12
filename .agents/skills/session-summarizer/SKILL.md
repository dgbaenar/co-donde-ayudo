---
name: session-summarizer
description: Use when creating a compact continuation handoff from verified repository and session state.
---

# Session summarizer

Create a compact handoff using [TEMPLATE.md](TEMPLATE.md).

1. Inspect current files and repository state relevant to the session.
2. Treat plans, intentions, user claims, and subagent reports as unverified until direct evidence confirms them.
3. Separate completed, partial, blocked, and pending work.
4. List only paths verified as changed and commands actually executed with their observed results.
5. Reference source documents instead of copying them.
6. Preserve unresolved decisions, approval boundaries, and the exact safe continuation point.
7. Name the next task only if it is already approved; otherwise state `not approved`.

Never promote missing output into a passing check or a proposed action into completed work.
