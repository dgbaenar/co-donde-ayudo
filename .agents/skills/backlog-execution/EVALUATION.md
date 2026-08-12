# Task evaluation

A task is complete only when every binary acceptance criterion passes with direct evidence, required checks exit successfully, blocking review findings are resolved, final files are inspected, and no unapproved scope was added.

A task is partial when useful in-scope work exists but one or more criteria lack evidence. It is blocked when a required decision, dependency, credential, permission, contract, or external state prevents safe progress.

## Report format

- Status: completed, partial, or blocked.
- Scope: task ID, allowed paths, exclusions.
- Evidence: exact commands and observed results.
- Criteria: one row per criterion with PASS or FAIL.
- Review: reviewer and blocking findings.
- Deviations: unplanned changes or `none`.
- Next: one unstarted, dependency-ready task or `not approved`.
