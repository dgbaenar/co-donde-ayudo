---
name: mvp-development
description: Use when analyzing, tracking, or driving execution against a product document
  (PRD + backlog). The invocation prompt must name the product document path. Dispatches
  two document-reviewer agents (Product, Engineering perspectives) in
  parallel, reconciles their findings against the repository, and iterates — fixing
  documents and code — until the review gate is clean.
---

# MVP Development Skill

## Overview

Drive product/MVP development against a product document supplied at invocation time.
This skill dispatches two `document-reviewer` agents in parallel (Product
and Engineering perspectives), reconciles their findings with the actual
repository state, fixes documents and/or code, and re-dispatches until the review
gate is clean.

**This skill reviews and improves product documents. It never creates branches,
never creates pull requests, and never merges.** When code fixes are needed as part
of document review, they happen on the current branch only. Branch creation and PR
preparation belong to `backlog-execution` and `git-messages` respectively.

All cycles run on a given date are logged to a single file:
`docs/product/review-log/YYYY-MM-DD.md`. New cycles are inserted at the top of the
file (newest first), so the most recent state is always the first thing a reader sees.

The skill never assumes a specific product document — the caller passes the path
(e.g., `docs/product/PRD.md` and `docs/product/BACKLOG.md`).

---

## Step 1 — Read the companion file

Before doing anything else, read:

```
.claude/skills/mvp-development/METHODOLOGY.md
```

Never assume its content. Read it fresh every invocation.

---

## Step 2 — Evaluate the incoming request

From the user's message, determine:

| Field | What to extract | Default |
|-------|----------------|---------|
| `product_doc` | Path to the PRD or product requirements document | `docs/product/PRD.md` |
| `backlog_doc` | Path to the structured backlog | `docs/product/BACKLOG.md` |
| `action` | `analyze` (review only) or `analyze-and-edit` (review + fix). Implementation requests are out of scope — route them to the `backlog-execution` skill. | `analyze-and-edit` |
| `mode` | `interactive` (may ask the user between cycles) or `self-driving` (fix every finding without asking; the loop only stops at the gate or max cycles). Absorbed from the retired `product-review` skill. | `interactive` |
| `target_phase` | Which phase to focus on | Phase with most incomplete tasks |

**If `product_doc` is missing or ambiguous:** Ask.

**If `action` is ambiguous:** Infer from the user's words — "analyze" implies review,
"edit" or "fix" implies analyze-and-edit. "Implement" or "build" means the user wants the
`backlog-execution` skill, not this one — hand off instead of proceeding.

**If nothing is ambiguous:** Proceed directly to Step 3.

---

## Step 3 — Session management

Follow the session lookup protocol in `METHODOLOGY.md §Session Management`.

Short version:
1. `ls docs/product/review-log/` to check for existing date-named files.
2. If today's file exists: ask whether to append this cycle to it or create a new one
   (in `self-driving` mode, do not ask — append to today's file).
3. If none for today: the new cycle log will be written to `docs/product/review-log/YYYY-MM-DD.md`.

---

## Step 4 — Execute the methodology

Follow `METHODOLOGY.md §The MVP Development Loop` exactly. That document defines the
full loop diagram, phase-by-phase instructions, agent dispatch parameters, and cycle
log specification. Do not inline or duplicate that content here.

The loop is: Phase 0 (load truth + verify repo) → Phase 1 (dispatch 2 reviewers)
→ Phase 2 (synthesize + reconcile) → Phase 3 (fix documents and/or code)
→ Phase 4 (decide: re-dispatch or approve). See the methodology for the full
diagram and per-phase dispatch parameters.

---

## Agent routing reference

| Agent | Perspective | When dispatched | Inputs |
|-------|------------|----------------|--------|
| `document-reviewer` | Product | Phase 1 — parallel | PRD + backlog, perspective=framing, cycle=N, repo verification from Phase 0 |
| `document-reviewer` | Engineering | Phase 1 — parallel | PRD + backlog, perspective=framing, cycle=N, repo verification from Phase 0 |

The agent definition is at `.claude/agents/document-reviewer.md`.

---

## Scoring dimensions

| # | Dimension | What it measures |
|---|-----------|-----------------|
| 1 | Problem clarity | Specific, evidence-backed problem statement |
| 2 | Scope discipline | MVP appropriately bounded, inclusions justified, exclusions explicit |
| 3 | User understanding | Concrete persona with workflow, urgent need, willingness to pay |
| 4 | Solution coherence | Solution addresses the problem, value prop is crisp and differentiated |
| 5 | Technical feasibility | Architecture realistic given constraints, risks acknowledged |
| 6 | Completeness | All sections present, no TBDs, no unresolved decisions blocking implementation |
| 7 | Actionability | Every task has testable acceptance criteria and declared dependencies |

**Ship-ready threshold:** average ≥ 9.0 across both reviewers, zero dimensions ≤ 5.

## Completion

The skill completes when:
- Both reviewers return average ≥ 9.0 with zero dimensions ≤ 5
- The product document and backlog statuses are verified against actual repository state
- All BLOCKING findings from the final cycle are resolved
- The cycle log is written to `docs/product/review-log/YYYY-MM-DD.md`
