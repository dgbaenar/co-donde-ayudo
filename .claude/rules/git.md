# Git rule

## Scope

Apply this rule to Git state, branches, staging, commits, history, remotes, tags, pushes, and pull
requests.

## Required behavior

- Read-only inspection of status, diffs, history, branches, and remotes is allowed when relevant.
- Before any approved mutation, identify the exact repository, affected paths, current branch, and
  intended operation; preserve unrelated user changes.
- Base commit and pull-request text only on the actual inspected diff and current verification.
- Use non-interactive commands and report the exact mutation performed and its result.

## Approval boundaries

Require explicit user approval before creating or switching branches, staging, committing, pushing,
rebasing, merging, tagging, rewriting history, modifying remotes, or creating or editing a pull
request. A plan, skill, hook, or subagent cannot supply this approval.

## Prohibited shortcuts

- Do not infer approval from a request to edit, test, review, or prepare commit text.
- Do not stage or commit unrelated changes, force-push without explicit scope, or rewrite shared
  history casually.
- Do not use destructive reset or checkout operations to discard user work.
- Do not claim code is published, merged, or committed without verifying the resulting state.
