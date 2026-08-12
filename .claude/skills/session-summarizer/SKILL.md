---
name: session-summarizer
description: Use at the end of a working session, when asked to "summarize the
  session", "write a session summary", "capture what we did", or "save context
  for next time". Produces a structured session summary under `memory/`
  (default, see Project configuration) that preserves what changed, what was
  decided, what went wrong, and what comes next, so a later session can resume
  without re-deriving it.
---

# Session Summarizer

## Overview

Produces a structured, concise session summary following the template in
`TEMPLATE.md`, written to a dated file so a session picking the work up later can
reconstruct the state without re-reading the whole history.

The summary is **evidence-based**: every claim about what was done, decided, or
left pending must be verifiable from the repository state (git log, open PRs,
task IDs in the diff, file changes). Anything remembered but not verifiable is
either checked before being written down or left out.

## Project configuration

This block is the **single canonical source** for every configurable value this
skill uses. Everything below refers to these variables by name (`${VAR}`); no
literal path, filename, or identifier from this block should be repeated anywhere
else in this file or in `TEMPLATE.md`. **To reuse this skill in another
repository, edit this block and nothing else needs to change** — with one
unavoidable exception: this file's own YAML `description` above names the
`SUMMARY_ROOT` default in prose, because skill discovery matches on keywords and
cannot substitute variables. Update that line too if you change it.

```
SKILL_ID = session-summarizer

SUMMARY_ROOT = memory
SUMMARY_FILENAME_FORMAT = YYYY-MM-DD.md
SUMMARY_ENTRY_TIME_FORMAT = HH:MM

BACKLOG_PATH = docs/product/BACKLOG.md
BACKLOG_TASK_ID_PATTERN = [A-Z]+-[0-9]+[A-Z]?
BACKLOG_GROUP_HEADING_PATTERN = ^## Épica
BACKLOG_SCOPE_COLUMNS = Pri, Tamaño

DECISION_LOG_PATH = docs/product/decisions
DECISION_ID_PATTERN = [a-z]+-[0-9]+[a-z]?

DEFAULT_BRANCH = main
RECENT_COMMIT_LIMIT = 10
```

| Variable | What it controls |
|---|---|
| `SKILL_ID` | This skill's own identifier, for self-reference and logging. Not a path. |
| `SUMMARY_ROOT` | Directory the dated summaries are written to. Must be a directory this skill owns; never point it at a directory another tool manages. |
| `SUMMARY_FILENAME_FORMAT` | Filename pattern of one day's summary inside `${SUMMARY_ROOT}`. One file per day, holding every session from that day. |
| `SUMMARY_ENTRY_TIME_FORMAT` | Timestamp that labels each session entry inside a day's file, so several sessions on one day stay distinguishable. |
| `BACKLOG_PATH` | The task backlog this project tracks work against. |
| `BACKLOG_TASK_ID_PATTERN` | Regex matching a task ID in this project, used to find which tasks a session touched. |
| `BACKLOG_GROUP_HEADING_PATTERN` | Regex matching the headings `${BACKLOG_PATH}` groups its tasks under. |
| `BACKLOG_SCOPE_COLUMNS` | The task-table columns that say when a task is due and how urgent it is. Reported alongside a touched task so the reader knows its weight. |
| `DECISION_LOG_PATH` | Document holding this project's architecture decision log, if it has one. Leave empty if not. |
| `DECISION_ID_PATTERN` | Regex matching a decision ID in `${DECISION_LOG_PATH}`. |
| `DEFAULT_BRANCH` | Branch feature work is compared against. |
| `RECENT_COMMIT_LIMIT` | How many commits to list when the branch has no divergence from `${DEFAULT_BRANCH}`. |

## Use when

- ending a working session
- the user asks to summarize the session, write a summary, or capture what was done
- the user says to save context for next time
- a long session produced decisions that would otherwise be lost

## Non-negotiable rules

- **Inspect, do not recall.** Run the inspection commands before writing. A claim
  that cannot be traced to repository state does not go in.
- **Be honest about mistakes.** If something went wrong, capture it, including
  work that was undone or reasoning that turned out to be wrong. A summary that
  only records successes is worse than none, because it hides the traps.
- **Distinguish done from verified.** Say which checks actually ran. Never let
  "written" read as "tested" or "deployed".
- **Keep it scannable.** A reader should get the state in about 30 seconds.
- **Do not duplicate the backlog.** Reference task IDs from `${BACKLOG_PATH}`;
  never restate their content or invent status for them.
- **Never include secrets.** No credentials, tokens, keys, or personal data.
- **Write for the next session, not for posterity.**

## One file per day, newest first

`${SUMMARY_ROOT}` holds one file per day, named `${SUMMARY_FILENAME_FORMAT}`.
There is no "current" or "latest" file: the most recent date is the latest, and a
filename never has to be renamed or rewritten as time passes.

Several sessions on the same day go in that same day's file, each as its own
entry headed by `${SUMMARY_ENTRY_TIME_FORMAT}`. **New entries go at the top**, so
the newest state is what a reader sees first and older entries are never edited.
This matches how this project already keeps its review logs.

Do not point `${SUMMARY_ROOT}` at a directory another tool writes to. If a memory
or note-taking plugin is installed, it maintains its own running buffer on its own
schedule, and two writers in one directory will clobber each other. Keep this
skill's output in a directory it owns.

## Required inspection

```bash
git branch --show-current
git log --oneline ${DEFAULT_BRANCH}..HEAD 2>/dev/null || git log --oneline -${RECENT_COMMIT_LIMIT}
git status --short
git diff --stat ${DEFAULT_BRANCH}...HEAD 2>/dev/null || git diff --stat HEAD
gh pr list --state open --json number,title,headRefName,isDraft 2>/dev/null
```

Then, to find what the session actually touched:

```bash
# Task IDs referenced in this branch's commits and diff
git log ${DEFAULT_BRANCH}..HEAD --format=%B 2>/dev/null | grep -oE "${BACKLOG_TASK_ID_PATTERN}" | sort -u
git diff ${DEFAULT_BRANCH}...HEAD 2>/dev/null | grep -oE "${BACKLOG_TASK_ID_PATTERN}" | sort -u

# Decision IDs added or changed, when DECISION_LOG_PATH is set
git diff ${DEFAULT_BRANCH}...HEAD -- ${DECISION_LOG_PATH} 2>/dev/null | grep -E "^\+" | grep -oE "${DECISION_ID_PATTERN}" | sort -u

# Today's file, to decide whether to create it or prepend to it
ls ${SUMMARY_ROOT}/ 2>/dev/null
```

Also scan the conversation for decisions, corrections, and dead ends that leave
no trace in git. These are usually the most valuable part of the summary and the
only part that cannot be recovered later.

## Writing procedure

1. Run the inspection commands and gather the evidence.
2. Open `TEMPLATE.md` for the section structure.
3. Fill each section using the guidelines below.
4. Write to `${SUMMARY_ROOT}/${SUMMARY_FILENAME_FORMAT}`. If that file already
   exists from an earlier session the same day, **insert this session's entry at
   the top**, under its own `${SUMMARY_ENTRY_TIME_FORMAT}` heading and followed by
   a `---` separator, leaving every earlier entry below it untouched.

### Section guidelines

**Backlog touchpoints.** Which task IDs matching `${BACKLOG_TASK_ID_PATTERN}` the
session touched, and what changed about each: created, advanced, blocked, or only
referenced. Include each task's `${BACKLOG_SCOPE_COLUMNS}` values so the reader
knows its weight without opening `${BACKLOG_PATH}`. Derive this from the diff and
commits, not from status markers, which many backlogs do not carry.

**Work done.** Chronological, grouped per branch:

```
## HH:MM | branch-name
- Accomplishment, one or two lines. PR number when there is one.
```

**Decisions.** One line each, with the reason:

```
- Decision: <what was chosen>. Why: <rationale, and what it was chosen over>.
```

Include the decision ID when one was recorded in `${DECISION_LOG_PATH}`.

**Mistakes and learnings.** Specific, not generic:

```
- Mistake: <what went wrong>. Cause: <why>. Fix: <what was done>.
- Learning: <what was learned>. Apply by: <how to avoid it next time>.
```

Reasoning that was wrong and then corrected belongs here, not just failures that
broke something. It is what stops the next session from repeating it.

**State at session end.** Facts only: current branch, open PRs with numbers and
whether they are drafts, and which verification actually ran versus which did not.

**Next steps.** Ordered by priority, specific enough that the first item can be
started without asking a question. Reference task IDs rather than restating work.

## Output

Write the summary to `${SUMMARY_ROOT}/${SUMMARY_FILENAME_FORMAT}`, then show the
user the Backlog touchpoints and Next steps sections so the state can be
corrected before the session ends.
