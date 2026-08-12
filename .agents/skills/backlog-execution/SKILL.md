---
name: backlog-execution
description: Use when selecting and executing one dependency-ready task from a user-supplied backlog in an existing repository.
---

# Backlog execution

Execute exactly one small, dependency-ready task from an explicit backlog path.

## PREFLIGHT

Read `AGENTS.md`, applicable rules, the explicit backlog, and current repository state. Confirm the task is authorized, its dependencies are evidenced, and required tools already exist. Never install dependencies or mutate Git or external systems implicitly.

## SELECT

Choose one task only. Prefer the smallest ready task that unlocks later work. Do not group adjacent tasks, infer completed dependencies, or expand scope while implementing.

## GATE

State task ID, allowed paths, excluded work, verified dependencies, binary acceptance criteria, verification commands, and approval-sensitive actions. Stop for approval when the task or repository guidance requires it.

## DISPATCH

Route implementation to the custom agent that owns the affected paths. Supply the complete contract. If ownership overlaps or required input is missing, stop as blocked.

## VERIFY

Run the narrow failing test before changing behavior, implement the minimum, then run scoped and relevant broader checks. Do not claim a configured tool ran unless its output was observed.

## REVIEW

Use a read-only verifier or reviewer independent of the implementer. Resolve blocking findings and re-run affected checks. Independently inspect final files; subagent reports are not proof.

## REPORT

Use [EVALUATION.md](EVALUATION.md). Report actual changed paths, commands and outputs, each criterion as pass or fail, deviations, and the next unstarted task. Never commit, push, create branches, or contact an external service without explicit approval.
