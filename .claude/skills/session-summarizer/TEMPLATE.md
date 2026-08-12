# {date}

_(One file per day. Each session on that day is an entry like the one below, newest at
the top, separated by `---`. Never edit an earlier entry.)_

## {time} — {one-line description of the session}

## Backlog touchpoints

| Task | Scope | What changed this session |
|------|-------|---------------------------|
| {task-id} | {scope-columns} | {created / advanced / blocked / referenced, one line} |

_(Task IDs match `BACKLOG_TASK_ID_PATTERN`; the Scope column carries that task's
`BACKLOG_SCOPE_COLUMNS` values from `BACKLOG_PATH`. Derive from the branch diff and
commits, not from status markers. Omit the table if the session touched no task.)_

## Work done

_(Chronological, grouped per branch. Timestamped `## HH:MM | branch` headings with
bullets underneath. One or two lines each, enough to reconstruct what happened.)_

## Decisions

_(One line each, with the reason and what it was chosen over. Include the decision ID
when one was recorded in `DECISION_LOG_PATH`.)_

- Decision: {what was chosen}. Why: {rationale}. {Decision ID, if any}

## Mistakes and learnings

_(Specific. Include reasoning that turned out to be wrong and was corrected, not only
things that broke.)_

- Mistake: {what went wrong}. Cause: {why}. Fix: {what was done}.
- Learning: {what was learned}. Apply by: {how to avoid it next time}.

## State at session end

- **Current branch:** {branch}
- **Open PRs:** {number, title, draft or ready}
- **Verified by:** {which checks actually ran}
- **Not verified:** {what was not checked, and why}

## Next steps

_(Prioritized. Specific enough that the first item can be started without asking a
question. Reference task IDs instead of restating the work.)_

1. {next action}
