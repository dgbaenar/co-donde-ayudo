# Engineering rule

## Scope

Apply this rule to source, tests, configuration, scripts, and structural changes.

## Required behavior

- Start from the active task's explicit scope and binary acceptance criteria.
- Inspect current files and configured commands before designing a change.
- Prefer the smallest implementation that fully satisfies the task. Keep modules cohesive, names
  specific, dependencies directed, and side effects explicit.
- Keep business rules, validation, persistence access, and external adapters in `src/backend/`.
  Keep presentation and user interaction in `src/frontend/`; communicate through an explicit
  backend-facing interface.
- Make surgical edits, preserve unrelated user changes, and inspect the final file content.
- Explain any necessary deviation from established structure and obtain approval when it expands
  scope or creates a new deployment boundary.

## Approval boundaries

Require explicit user approval before broad refactors, new architectural layers, new deployment
boundaries, or edits outside the approved task paths.

## Prohibited shortcuts

- Do not implement speculative abstractions, future requirements, or unrelated cleanup.
- Do not hide mutable global state, perform operational work at import time, or couple backend code
  to UI frameworks.
- Do not bypass package ownership with persistence access from frontend code.
- Do not overwrite unrelated changes or present an intended diff as verified final state.
