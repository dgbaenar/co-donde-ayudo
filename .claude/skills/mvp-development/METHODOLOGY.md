# MVP Development Methodology

This document is the authoritative methodology for driving MVP development against
the PRD and Backlog. The `mvp-development` skill reads this file at activation time.
Never inline or assume its content — always read it fresh.

---

## Directory Pattern

```
docs/product/
├── PRD.md                          ← product requirements document
├── BACKLOG.md                      ← structured task backlog
└── review-log/                     ← cycle logs
    └── YYYY-MM-DD.md               ← one file per date, contains all cycles from that date

.claude/
├── skills/mvp-development/
│   ├── SKILL.md                    ← thin — references this file
│   └── METHODOLOGY.md              ← this file
└── agents/
    └── document-reviewer.md ← scoring agent (2 perspectives)
```

Cycle logs live under `docs/product/review-log/`. Product documents live under
`docs/product/`. These directories are never mixed.

---

## Session Management

### What is a cycle?

A cycle is one complete pass through the loop: verify → dispatch reviewers →
synthesize → fix → decide. Each cycle is appended to a date-named log file.

### Cycle log location

```
docs/product/review-log/YYYY-MM-DD.md
```

### Session lookup protocol

When the `mvp-development` skill is invoked:

**Step A:** Check for existing date-named files:

```bash
ls docs/product/review-log/
```

**Step B:** If today's file exists:
- Ask the user:
  > "Today's review log (`YYYY-MM-DD.md`) already exists. Append this cycle to it,
  > or create a new file?"
- Wait for the user's response before writing.

**Step C:** If today's file does not exist:
- Create `docs/product/review-log/YYYY-MM-DD.md`.
- Start the first cycle entry.

**Step D:** Each new cycle appends to the selected file. No separate session
directories — the date file IS the session for that day.

---

## Agent Routing

The skill uses one agent type from two perspectives. Both run in parallel.

| Perspective | Agent | Primary question | Weighted dimensions |
|-------------|-------|-----------------|-------------------|
| Product | `document-reviewer` | Would a target user pay for or meaningfully adopt this based on what the documents describe? | 1, 2, 3, 4 |
| Engineering | `document-reviewer` | Can an engineer build this without asking for clarification? | 5, 6, 7 |

### Agent dispatch parameters

**document-reviewer** receives: the current content of `PRD.md` and
`BACKLOG.md`, the assigned perspective (Product or Engineering), the
cycle number, and the repository verification report from Phase 0 (so the
Engineering reviewer can flag status mismatches and the Product reviewer can
verify claims against real code).

Each reviewer returns:
- Scores for all 7 dimensions (0–10) with section-cited evidence
- Top 3 strengths with citations
- Top 3 weaknesses with citations
- Critical gap (dimension scored ≤ 5 with the most downstream impact)
- Ordered recommendations

---

## The MVP Development Loop

```
┌───────────────────────────────────────────────────────────┐
│  Phase 0: Load truth + verify repo state                  │
│      │                                                    │
│      ▼                                                    │
│  Phase 1: Dispatch 2 reviewers (parallel)                 │
│      │  document-reviewer × Product               │
│      │  document-reviewer × Engineering           │
│      │                                                    │
│      ▼                                                    │
│  Phase 2: Synthesize findings + reconcile                 │
│      │                                                    │
│      ▼                                                    │
│  Phase 3: Fix — edit documents and/or code                │
│      │                                                    │
│      ▼                                                    │
│  Phase 4: Decide                                          │
│      │                                                    │
│      ├── Avg < 9.0 or any dim ≤ 5? ──► Loop to Phase 0   │
│      │                                                    │
│      ▼ Avg ≥ 9.0, zero dims ≤ 5                          │
│  APPROVED — conclude                                      │
└───────────────────────────────────────────────────────────┘
```

**Maximum 5 cycles.** Beyond that, remaining gaps are fundamental and need
external resolution (technical experimentation, a human decision, etc.).

---

### Phase 0: Load Truth + Verify Repo State

1. Read the PRD and Backlog in full.
2. Read `CLAUDE.md` for project constraints.
3. Read `.claude/rules/engineering/` for hard rules.
4. For every task in the current phase:
   - Verify status claims against actual code, schema, tests.
   - Note evidence at `file:line` granularity.
   - Flag any mismatch: a ✅ that regressed, a ❌ that was partially built, etc.
5. Produce a **repository verification report** — a table of every task with
   actual status (✅/🟡/❌/🔴), evidence location, and any drift notes.
   This report is passed to the Engineering reviewer in Phase 1.

---

### Phase 1: Dispatch 2 Reviewers (Parallel)

Launch two `document-reviewer` agents simultaneously:

**Agent 1 — Product perspective:**
> "Review docs/product/PRD.md and docs/product/BACKLOG.md from the PRODUCT
> perspective. Cycle number: N."

**Agent 2 — Engineering perspective:**
> "Review docs/product/PRD.md and docs/product/BACKLOG.md from the ENGINEERING
> perspective. Cycle number: N. Additionally, here is a repository verification
> report from Phase 0 that flags status mismatches between the documents and
> the actual codebase — use it to ground your scores in verified facts:
> [verification report]"

Each returns: 7 dimension scores with section citations, top 3 strengths, top 3
weaknesses, critical gap, and ordered recommendations.

---

### Phase 2: Synthesize Findings + Reconcile

Combine the two reviews into a single report:

1. Compute average per dimension and overall.
2. Determine verdict:
   - ✅ APPROVED: avg ≥ 9.0, zero dimensions ≤ 5
   - ⚠️ CONDITIONAL: avg ≥ 7.0, fix critical gap and re-review
   - 🔴 NEEDS WORK: avg < 7.0, substantial rewrite required
3. Identify consensus strengths (cited by ≥ 2 reviewers).
4. Identify consensus weaknesses (cited by ≥ 2 reviewers).
5. Pinpoint the critical gap — the finding with the most downstream impact.
6. Cross-reference reviewer findings against the repo verification report.
   A reviewer citing "missing schema" when the table actually exists in code is
   a finding to ignore. A reviewer missing a real code drift is a finding to add.

---

### Phase 3: Fix

Address every finding. Prioritize:

1. **The critical gap** — fix it first.
2. **Every weakness cited by ≥ 2 reviewers.**
3. **Every recommendation that is actionable** (add missing sections, define
   missing schemas, resolve open questions, add missing tasks, sharpen
   acceptance criteria).
4. **Repository drift** — if the Phase 0 verification found code that doesn't
   match the documents, either update the documents or fix the code.
5. **Status mismatches** — if a task is marked ✅ but the code doesn't exist,
   or marked ❌ but partially built, update the backlog.

If a recommendation cannot be resolved (e.g., "interview customers"), document
the hypothesis, the plan to test it post-deploy, and the success criteria.

**After every fix batch, update the cycle log** with what was changed before
proceeding to Phase 4.

---

### Phase 4: Decide

- **If APPROVED (avg ≥ 9.0, zero dims ≤ 5):** write the final cycle entry.
  The documents are approved for implementation. Stop.

- **If NOT approved and cycles < 5:** go back to Phase 0. Re-verify, re-dispatch,
  re-fix. Do not ask the user — just loop.

- **If NOT approved and cycles = 5:** write the final cycle entry documenting
  remaining gaps. These are fundamental and need external resolution. Present
  to user and stop.

**Score regression is a bug.** If a fix drops a previously passing dimension
below 5, revert that specific change and note it in the cycle log.

---

## Cycle Log Specification

The cycle log is mandatory. It records every cycle's scores, findings, changes
made, and unresolved items. It is written appending to a date-named file.

### Location

```
docs/product/review-log/YYYY-MM-DD.md
```

### Format

Each cycle appends to the file. The format is structured but not rigid:

```markdown
# Product Review Log — YYYY-MM-DD

**Documents under review:** [`PRD.md`](../PRD.md), [`BACKLOG.md`](../BACKLOG.md)

---

## Cycle N — YYYY-MM-DD HH:MM

**Verdict:** ✅ APPROVED / ⚠️ CONDITIONAL / 🔴 NEEDS WORK

### Scores

| # | Dimension | Product | Engineering | Avg | Status |
|---|-----------|---------|-------------|-----|--------|
| 1 | Problem clarity | X/10 | X/10 | X.X | |
| ... | ... | ... | ... | ... | ... |
| **Overall** | **X.X** | **X.X** | **X.X** | |

### Strengths (consensus)
- ...

### Weaknesses (consensus)
- ...

### Critical gap
- ...

### Repository verification (Phase 0 findings)
- Task P0-NN: document says ✅, actual code shows 🟡 — evidence at `file:line`
- ...

### Changes made in this cycle
- ...

### Unresolved (deferred to next cycle)
- ...

---
```

### Ordering

- **Newest cycle first.** Each new cycle is inserted at the top of the review history,
  immediately after the header and before the previous cycle. The most recent state is
  always the first thing a reader sees.
- **All cycles live in one file per date.** `docs/product/review-log/YYYY-MM-DD.md`
  contains every cycle run on that date, newest first. No separate files per cycle.

### Rules

- **Write each cycle entry before starting the next cycle.** Never retroactively.
- **Record specific file:line evidence**, not general observations.
- **Record drift explicitly** — if implementation diverges from plan, say so.
- **Do not edit previous cycle entries.** New cycles are inserted above, older
  entries are never modified.
