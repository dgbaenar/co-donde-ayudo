---
name: git-messages
description: Use when writing or reviewing commit messages, pull-request titles, descriptions, or branch summaries from actual repository state.
---

# Git messages

Produce text only. Never create a branch, commit, tag, push, pull request, or other Git mutation.

1. Confirm the directory is a Git repository.
2. Inspect actual status and relevant staged or unstaged diff. User summaries and agent reports are context, not verified state.
3. If repository evidence is unavailable, state the limitation and request the diff or status needed for an exact message.
4. Describe only observed changes, tests, risks, and breaking behavior. Do not invent test results.
5. Use [template.md](template.md), remove unused sections, and avoid placeholders.
6. Run `scripts/validate.sh` against the draft subject or message file when possible.

Prefer a Conventional Commit subject with an imperative summary. Keep the subject at most 72 characters.
