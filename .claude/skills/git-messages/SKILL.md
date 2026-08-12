---
name: git-messages
description: Use when asked to write, improve, or review git commit messages, Conventional Commit subjects or bodies, pull request titles, or pull request descriptions from the actual branch diff and repository context.
---

# Commit and PR Writer

Use this skill to produce evidence-based Git communication from the real branch state.

This is the designated final-step skill for commit message and pull request
preparation. Development skills (`backlog-execution`, `mvp-development`, `run-experiment`)
commit on feature branches but do not compose PR descriptions or open PRs — that
happens here, when the user explicitly decides the work is ready to ship.

## Use when

- a commit message is needed
- a pull request title or description is needed
- a Conventional Commit rewrite is requested
- a branch summary for reviewers is requested
- help choosing the correct commit type or scope is needed
- a review of whether staged changes should be split is requested

## Non-negotiable rules

- **Never open a pull request without explicit user confirmation.** Compose the
  title and description, present them, and ask whether to proceed. Do not open
  the PR unless the user says yes.
- Inspect the repository state before writing.
- Base the message only on evidence from Git and repository files.
- Do not invent tests, validation, benchmarks, user impact, or architectural intent.
- Prefer the narrowest truthful summary.
- Preserve repository terminology exactly.
- If the branch mixes unrelated work, say so — then still produce the most coherent truthful summary.
- Do not default to `feat` or `fix` when a more accurate type exists.

## Required inspection

```bash
git branch --show-current
git log --oneline -10
git status --short
git diff --stat HEAD
git diff --cached --stat
git diff HEAD
git diff --cached
```

Also scan for project conventions:
- `CLAUDE.md`, `CONTRIBUTING.md`, or `.github/PULL_REQUEST_TEMPLATE.md`
- Existing commit subjects in `git log` for scope and type patterns

## Conventional Commits

### Type selection

| Type | When to use |
|------|-------------|
| `feat` | A new user-facing capability |
| `fix` | A bug correction |
| `refactor` | Code changed with no behavior change |
| `docs` | Documentation only |
| `test` | Tests added or modified |
| `build` | Build system, dependencies, CI |
| `chore` | Tooling, config, scripts |
| `style` | Formatting only, no logic change |
| `perf` | Measurable performance improvement |
| `revert` | Reverts a prior commit |

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Subject line:**
- 72 characters max
- Imperative mood: "add", not "added" or "adds"
- No period at end
- Lowercase after the colon

**Body:**
- Wrap at 72 characters
- Explain *why*, not *what* (the diff already shows what changed)
- Separate from subject with a blank line
- Omit if the subject alone is sufficient

**Footer:**
- `BREAKING CHANGE: <description>` if applicable
- `Closes #N` for issue references

### Scope

Derive from the directory, package, or domain most affected (`auth`, `api`, `ui`, `infra`). Omit rather than guess.

## PR description

### Required sections

1. **Summary** — 2–4 sentences: what changed and why
2. **Changes** — bulleted list of meaningful changes (skip trivial file renames)
3. **Test plan** — verifiable steps only; omit if no tests exist in the diff

### Prohibited content

- Test claims when no tests appear in the diff
- Performance claims without benchmarks visible in the diff
- "This PR improves..." without evidence
- Future work promises
- Line-by-line narration of what the code does

## Branch naming

```
{github-username}/{short-slug}
```

- `{github-username}` — the GitHub username of the person doing the work (look up
  with `gh api user --jq .login` or use the authenticated user)
- `{short-slug}` — lowercase kebab-case, max ~50 chars. For backlog-driven work,
  derive from the task ID(s)/Épica and purpose (e.g., `data-03-raw-store-fixtures`,
  matching the grouping `backlog-execution` derives from `docs/product/BACKLOG.md`).
  For ad-hoc work, derive from the change itself.
- Example: `dgbaenar/data-03-raw-store-fixtures`, `dgbaenar/fix-pit-cutoff-boundary`

Do **not** use `feature/`, `fix/`, or other type prefixes. The username prefix
already provides the namespace.

## When to recommend splitting

Flag and explain if:
- The diff touches unrelated systems or domains
- A refactor is bundled with a feature or bug fix
- Multiple unrelated control IDs or modules are modified

Still produce a message for the current state. Add the split recommendation after.

## Output

1. Commit subject (always)
2. Commit body (when warranted by complexity or non-obvious intent)
3. For PRs: title + full description using `template.md` structure

See `examples/sample.md` for a concrete reference output.
