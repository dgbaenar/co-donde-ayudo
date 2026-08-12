# Testing rule

## Scope

Apply this rule to behavior changes, defect fixes, refactors with behavioral risk, and completion
claims.

## Required behavior

- Derive tests from the active task's acceptance criteria and critical invariants.
- Before implementing a behavior change, add or identify a focused test and run it to observe the
  expected failure. Then implement only enough behavior to make it pass and refactor while green.
- Test meaningful public behavior instead of incidental implementation details.
- Keep backend tests in `tests/backend/`, frontend tests in `tests/frontend/`, and boundary-spanning
  tests in `tests/integration/`.
- Use local fakes and synthetic fixtures for external systems by default.
- Run current checks and report exact commands, outcomes, skipped checks, and blockers.

## Approval boundaries

Obtain explicit approval before using a real external service, private dataset, paid test resource,
or command that installs missing test tooling.

## Prohibited shortcuts

- Do not write implementation first and add a passing test afterward for a behavior change.
- Do not weaken, delete, skip, or rewrite a failing assertion merely to obtain a green result.
- Do not substitute mocks for the behavior under test or call an external system when a local fake
  can establish the criterion.
- Do not claim a check passed from stale output, another agent's statement, or an unexecuted command.
