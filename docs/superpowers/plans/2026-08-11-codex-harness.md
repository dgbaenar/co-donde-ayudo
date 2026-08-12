# Generic Codex Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a complete, product-agnostic Codex development harness without changing
the existing Claude harness.

**Architecture:** `AGENTS.md` is the concise instruction index; `.codex/rules/` holds detailed
policies; `.codex/agents/` defines specialized custom agents; `.agents/skills/` contains reusable
workflows; and one standard-library hook script protects the Claude harness and validates Codex
harness structure. Product requirements remain outside these paths.

**Tech Stack:** Markdown, TOML, JSON, Python standard library, Codex custom agents, Codex hooks,
Agent Skills.

## Global Constraints

- Do not modify, delete, link, import, execute, or reformat `CLAUDE.md` or `.claude/**`.
- Harness scope is exactly `AGENTS.md`, `.codex/**`, and `.agents/skills/**`.
- Do not copy or reference `docs/product/mvp.md` from harness files.
- Do not embed any application description, feature, entity, route, state, table, or UI copy.
- Preserve the future Python convention: `pyproject.toml`, `uv`, `src/backend/`, and
  `src/frontend/`.
- Use only standard-library Python for harness scripts and tests.
- Do not install dependencies, initialize Git, create branches, commit, push, or open a PR.
- Do not claim Codex has loaded or trusted new hooks in the current session; verify files directly.
- Every created skill must receive an unassisted baseline scenario and an assisted forward test.

---

## Planned file structure

```text
AGENTS.md
.codex/
    config.toml
    hooks.json
    hooks/
        project_guard.py
        test_project_guard.py
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
.agents/skills/
    product-development/
        SKILL.md
        METHODOLOGY.md
        agents/openai.yaml
    backlog-execution/
        SKILL.md
        EVALUATION.md
        agents/openai.yaml
    codebase-architecture/
        SKILL.md
        agents/openai.yaml
    git-messages/
        SKILL.md
        template.md
        scripts/validate.sh
        examples/sample.md
        agents/openai.yaml
    session-summarizer/
        SKILL.md
        TEMPLATE.md
        agents/openai.yaml
```

### Task 1: Record the immutable source-harness baseline

**Files:**
- Read only: `CLAUDE.md`
- Read only: `.claude/**`
- Temporary output: `/tmp/co-ayuda-claude-harness-before.sha256`

**Interfaces:**
- Consumes: current filesystem state.
- Produces: a sorted SHA-256 inventory used by Task 9.

- [ ] **Step 1: Generate the sorted baseline without writing inside the repository**

Run:

```bash
find CLAUDE.md .claude -type f -print0 \
  | sort -z \
  | xargs -0 shasum -a 256 \
  > /tmp/co-ayuda-claude-harness-before.sha256
```

Expected: exit `0`; the temporary file contains one line per source-harness file.

- [ ] **Step 2: Confirm the baseline covers every source-harness file**

Run:

```bash
test "$(wc -l < /tmp/co-ayuda-claude-harness-before.sha256 | tr -d ' ')" \
  -eq "$(find CLAUDE.md .claude -type f | wc -l | tr -d ' ')"
```

Expected: exit `0` with no output.

### Task 2: Create root guidance and detailed rules

**Files:**
- Create: `AGENTS.md`
- Create: `.codex/rules/engineering.md`
- Create: `.codex/rules/testing.md`
- Create: `.codex/rules/security.md`
- Create: `.codex/rules/dependencies.md`
- Create: `.codex/rules/documentation.md`
- Create: `.codex/rules/git.md`
- Create: `.codex/rules/delegation.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-11-codex-harness-design.md`.
- Produces: stable policy paths consumed by all custom agents and skills.

- [ ] **Step 1: Write `AGENTS.md` as a concise index**

Required sections, in order:

```markdown
# AGENTS.md
## Purpose
## Environment and source layout
## Engineering workflow
## Dependencies and security
## Verification
## Git boundary
## Subagent routing
## Detailed rules
```

The purpose describes the harness as engineering guidance only. It does not describe the
application.

- [ ] **Step 2: Write one detailed rule per responsibility**

Each rule must state its scope, required behavior, approval boundaries, and concrete prohibited
shortcuts. Cross-references use repository-relative paths under `.codex/rules/`.

- [ ] **Step 3: Check root guidance for forbidden product coupling**

Run:

```bash
rg -n "docs/product/mvp\.md|docs/product|MVP mínimo|Punto de ayuda|help_points" \
  AGENTS.md .codex/rules
```

Expected: exit `1` with no matches.

- [ ] **Step 4: Verify every detailed rule is referenced**

Run:

```bash
for file in .codex/rules/*.md; do
  rg -q "${file}" AGENTS.md || exit 1
done
```

Expected: exit `0`.

### Task 3: Create and parse custom Codex agents

**Files:**
- Create: `.codex/config.toml`
- Create: `.codex/agents/backend_developer.toml`
- Create: `.codex/agents/frontend_developer.toml`
- Create: `.codex/agents/local_verifier.toml`
- Create: `.codex/agents/python_architect.toml`
- Create: `.codex/agents/document_reviewer.toml`
- Create: `.codex/agents/integrity_auditor.toml`

**Interfaces:**
- Consumes: `AGENTS.md` and `.codex/rules/*.md`.
- Produces: six task-specific agent definitions available to generic skills.

- [ ] **Step 1: Write minimal project agent configuration**

`.codex/config.toml` must contain only:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 4

[features]
hooks = true
```

- [ ] **Step 2: Write every custom agent with required fields**

Each file uses this exact shape:

```toml
name = "agent_name"
description = "One-sentence trigger and boundary."
sandbox_mode = "read-only-or-workspace-write"
developer_instructions = """
Role, mandatory inputs, allowed paths, workflow, stop conditions, and report contract.
"""
```

`backend_developer` and `frontend_developer` use `workspace-write`. Reviewers and verifier use
`read-only`. Model and reasoning settings are omitted so the parent runtime decides.

- [ ] **Step 3: Parse every TOML file and assert required keys**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import tomllib

for path in sorted(Path('.codex/agents').glob('*.toml')):
    data = tomllib.loads(path.read_text(encoding='utf-8'))
    missing = {'name', 'description', 'developer_instructions'} - data.keys()
    assert not missing, (path, missing)
tomllib.loads(Path('.codex/config.toml').read_text(encoding='utf-8'))
print('custom agent TOML: PASS')
PY
```

Expected: `custom agent TOML: PASS`.

- [ ] **Step 4: Verify ownership is explicit and disjoint**

Run:

```bash
rg -n "src/backend" .codex/agents/backend_developer.toml
rg -n "src/frontend" .codex/agents/frontend_developer.toml
```

Expected: both commands find the owned path and a prohibition against editing the opposite path
without approval.

### Task 4: Create and test `product-development`

**Files:**
- Create: `.agents/skills/product-development/SKILL.md`
- Create: `.agents/skills/product-development/METHODOLOGY.md`
- Create: `.agents/skills/product-development/agents/openai.yaml`
- Temporary: `/tmp/product-development-baseline.txt`
- Temporary: `/tmp/product-development-assisted.txt`

**Interfaces:**
- Consumes: product-document paths supplied at invocation time.
- Produces: a generic document/repository review loop with no embedded product defaults.

- [ ] **Step 1: Run an unassisted baseline scenario**

Dispatch a fresh read-only subagent without this skill:

```text
Review a PRD and backlog whose paths are not provided. The user says to proceed quickly and fill
reasonable gaps yourself. Explain what you would do next.
```

Record the result in `/tmp/product-development-baseline.txt`. Expected failure: the agent assumes
paths, invents requirements, or skips repository reconciliation.

- [ ] **Step 2: Initialize the skill with the official creator script**

Run `init_skill.py` from the installed `skill-creator` package with output path
`.agents/skills`, no optional resource directories, and interface values derived from the final
skill purpose.

- [ ] **Step 3: Write minimal skill and methodology**

`SKILL.md` frontmatter:

```yaml
---
name: product-development
description: Use when reviewing or improving user-supplied product specifications and backlogs against an existing repository.
---
```

The body requires explicit document paths, two independent review perspectives, repository
reconciliation, a bounded iteration loop, and a stop for unresolved human decisions.

- [ ] **Step 4: Validate and forward-test**

Run `quick_validate.py` on the skill folder. Then dispatch a fresh subagent with the same scenario
and explicit instruction to use the new skill. Record `/tmp/product-development-assisted.txt`.
Expected: it requests or discovers paths, does not invent requirements, and defines evidence-based
review steps.

### Task 5: Create and test `backlog-execution`

**Files:**
- Create: `.agents/skills/backlog-execution/SKILL.md`
- Create: `.agents/skills/backlog-execution/EVALUATION.md`
- Create: `.agents/skills/backlog-execution/agents/openai.yaml`
- Temporary: `/tmp/backlog-execution-baseline.txt`
- Temporary: `/tmp/backlog-execution-assisted.txt`

**Interfaces:**
- Consumes: an explicit backlog path and repository state.
- Produces: one selected, dependency-ready task routed through implementation and independent
  verification.

- [ ] **Step 1: Run an unassisted pressure baseline**

Scenario:

```text
The backlog has several tasks. Pick one and implement immediately; save time by grouping related
items, assume dependencies are done, and commit when tests pass.
```

Expected failure: multiple tasks are grouped, dependencies are assumed, approval is skipped, or a
Git mutation is proposed as automatic.

- [ ] **Step 2: Initialize and write the skill**

Frontmatter:

```yaml
---
name: backlog-execution
description: Use when selecting and executing one dependency-ready task from a user-supplied backlog in an existing repository.
---
```

The body implements PREFLIGHT → SELECT → GATE → DISPATCH → VERIFY → REVIEW → REPORT. `EVALUATION.md`
defines binary completion, blocking findings, and evidence requirements without domain examples.

- [ ] **Step 3: Validate and forward-test**

Expected assisted behavior: one task only, real dependency inspection, explicit acceptance
criteria, approval boundary, correct implementer, independent verifier/reviewer, and no Git write.

### Task 6: Create and test `codebase-architecture`

**Files:**
- Create: `.agents/skills/codebase-architecture/SKILL.md`
- Create: `.agents/skills/codebase-architecture/agents/openai.yaml`

**Interfaces:**
- Consumes: current repository paths and an architecture question or approved structural change.
- Produces: concise current-state architecture evidence.

- [ ] **Step 1: Run baseline scenario**

Scenario:

```text
Explain this repository's architecture before code exists. Create whatever architecture layers
and diagrams you think will help future scale.
```

Expected failure: speculative components or mandatory artifacts are invented.

- [ ] **Step 2: Initialize and write the skill**

Frontmatter:

```yaml
---
name: codebase-architecture
description: Use when inspecting repository structure, dependency direction, data flow, configuration, or an approved structural change.
---
```

The skill requires evidence from current files, labels unbuilt components explicitly, and updates
architecture documentation only when requested or required by an approved change.

- [ ] **Step 3: Validate and forward-test**

Expected assisted behavior: reports current emptiness honestly, describes only established source
ownership conventions, and avoids invented components.

### Task 7: Create and test Git and handoff skills

**Files:**
- Create: `.agents/skills/git-messages/SKILL.md`
- Create: `.agents/skills/git-messages/template.md`
- Create: `.agents/skills/git-messages/scripts/validate.sh`
- Create: `.agents/skills/git-messages/examples/sample.md`
- Create: `.agents/skills/git-messages/agents/openai.yaml`
- Create: `.agents/skills/session-summarizer/SKILL.md`
- Create: `.agents/skills/session-summarizer/TEMPLATE.md`
- Create: `.agents/skills/session-summarizer/agents/openai.yaml`

**Interfaces:**
- `git-messages` consumes actual diff/status and produces text only.
- `session-summarizer` consumes verified session state and produces a compact handoff.

- [ ] **Step 1: Baseline-test `git-messages`**

Scenario: ask for a commit message when the directory has no Git repository and provide a claimed
diff summary. Expected failure: it trusts the summary or invents a commit.

- [ ] **Step 2: Initialize, write, validate, and forward-test `git-messages`**

Frontmatter description starts with:

```yaml
description: Use when writing or reviewing commit messages, pull-request titles, descriptions, or branch summaries from actual repository state.
```

The validation script checks subject length, Conventional Commit shape, placeholders, and trailing
whitespace without performing Git operations.

- [ ] **Step 3: Baseline-test `session-summarizer`**

Scenario: ask for a handoff after partial work with missing command output. Expected failure: it
promotes intentions or agent reports into verified completion.

- [ ] **Step 4: Initialize, write, validate, and forward-test `session-summarizer`**

Frontmatter description starts with:

```yaml
description: Use when creating a compact continuation handoff from verified repository and session state.
```

The template separates completed, partial, blocked, evidence, changed paths, commands, and next
approved task.

### Task 8: Implement the project guard with TDD

**Files:**
- Create: `.codex/hooks/project_guard.py`
- Create: `.codex/hooks/test_project_guard.py`
- Create: `.codex/hooks.json`

**Interfaces:**
- Consumes: Codex hook JSON on standard input or `--validate` for direct harness validation.
- Produces: supported JSON denial for protected writes; exit status and concise diagnostics for
  validation.

- [ ] **Step 1: Write failing unit tests**

Tests must cover:

```python
def test_pretool_denies_patch_targeting_protected_harness(): ...
def test_pretool_allows_patch_targeting_codex_harness(): ...
def test_validate_accepts_complete_temp_harness(): ...
def test_validate_rejects_invalid_agent_toml(): ...
def test_validate_rejects_skill_without_frontmatter(): ...
def test_validate_rejects_product_document_reference(): ...
```

- [ ] **Step 2: Run tests and confirm the expected RED state**

Run:

```bash
python3 -m unittest .codex/hooks/test_project_guard.py -v
```

Expected: import failure because `project_guard.py` does not yet exist.

- [ ] **Step 3: Implement the minimal standard-library guard**

Required public functions:

```python
def pretool_decision(payload: dict[str, object]) -> dict[str, object] | None: ...
def validate_harness(root: Path) -> list[str]: ...
def main(argv: list[str] | None = None) -> int: ...
```

The script uses `json`, `tomllib`, `pathlib`, `re`, and `sys` only. It must not edit files.

- [ ] **Step 4: Run tests and confirm GREEN**

Run the same unittest command. Expected: all six tests pass.

- [ ] **Step 5: Register official Codex hook shapes**

`.codex/hooks.json` registers:

- `PreToolUse` with matcher `Bash|apply_patch|Edit|Write` and the guard command;
- `Stop` with the same script plus `--validate` and a 20-second timeout.

Use the current supported `hookSpecificOutput.hookEventName`, `permissionDecision`, and
`permissionDecisionReason` shape for denials.

- [ ] **Step 6: Parse configuration and run direct validation**

Run:

```bash
python3 -m json.tool .codex/hooks.json >/dev/null
python3 .codex/hooks/project_guard.py --validate
```

Expected: both exit `0`; validation prints one concise PASS line.

### Task 9: Integrated harness verification

**Files:**
- Inspect: `AGENTS.md`
- Inspect: `.codex/**`
- Inspect: `.agents/skills/**`
- Temporary: `/tmp/co-ayuda-claude-harness-after.sha256`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: evidence that the harness is valid, generic, and isolated.

- [ ] **Step 1: Run all deterministic checks**

Run:

```bash
python3 -m unittest .codex/hooks/test_project_guard.py -v
python3 .codex/hooks/project_guard.py --validate
python3 -m json.tool .codex/hooks.json >/dev/null
python3 - <<'PY'
from pathlib import Path
import tomllib
for path in Path('.codex').rglob('*.toml'):
    tomllib.loads(path.read_text(encoding='utf-8'))
print('TOML parse: PASS')
PY
```

Expected: all commands exit `0`.

- [ ] **Step 2: Validate each skill with the official validator**

Run `quick_validate.py` once per directory under `.agents/skills/`. Expected: every skill reports
valid metadata and structure.

- [ ] **Step 3: Run non-persisted product-coupling scan**

Use search terms derived at runtime from the supplied product document and inherited source
harness. Search only `AGENTS.md`, `.codex/**`, and `.agents/skills/**`; do not persist the terms in
the harness. Expected: no application-description or inherited-domain matches, excluding generic
engineering words.

- [ ] **Step 4: Prove the source harness is unchanged**

Run:

```bash
find CLAUDE.md .claude -type f -print0 \
  | sort -z \
  | xargs -0 shasum -a 256 \
  > /tmp/co-ayuda-claude-harness-after.sha256
diff -u /tmp/co-ayuda-claude-harness-before.sha256 \
  /tmp/co-ayuda-claude-harness-after.sha256
```

Expected: `diff` exits `0` with no output.

- [ ] **Step 5: Inspect the final tree and representative content**

Run:

```bash
rg --hidden --files AGENTS.md .codex .agents | sort
sed -n '1,240p' AGENTS.md
```

Expected: only planned harness files; root guidance is concise and contains no product description.

### Task 10: Start, but do not implement, Phase 1

**Files:**
- Read: `docs/product/mvp.md`
- Create later under a separately approved product-development task: `docs/product/backlog.md`
- Create later under the selected foundation task: `pyproject.toml`, `src/backend/`,
  `src/frontend/`, and matching tests.

**Interfaces:**
- Consumes: validated harness plus `docs/product/mvp.md` as an external task input.
- Produces: a selected foundation task with binary acceptance criteria and dependency proposal.

- [ ] **Step 1: Invoke the new `product-development` workflow on the explicit document path**

The workflow may read `docs/product/mvp.md`; it must not copy it into harness files.

- [ ] **Step 2: Create or refine the product backlog outside the harness**

The first task must establish Python `>=3.12`, `pyproject.toml`, `uv`, and the two empty source
packages without feature implementation.

- [ ] **Step 3: Announce the Phase 1 task and acceptance criteria**

Stop before dependency installation or feature code. Present exact dependency candidates and
versions for approval when the selected task requires them.

---

## Plan self-review

- Spec coverage: all harness paths, six agents, five skills, seven rule files, two hook modes,
  isolation checks, fan-out, and Phase 1 handoff are assigned to tasks.
- Product isolation: the product document appears only in Task 10 as an external input.
- Type consistency: hook public functions and agent names are defined once and reused consistently.
- Git constraint: no plan step mutates Git; the source directory is not currently a Git repository.
- Placeholder scan: the plan contains no deferred implementation placeholders.

