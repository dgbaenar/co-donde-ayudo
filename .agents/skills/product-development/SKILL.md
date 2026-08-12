---
name: product-development
description: Use when reviewing or improving user-supplied product specifications and backlogs against an existing repository.
---

# Product development

Review supplied documents without embedding assumptions about any application.

## Required inputs

Require explicit specification and backlog paths. If paths are absent, discover plausible candidates, report them, and obtain confirmation before treating any as authoritative. Also require the repository root and the requested output: review only, document edits, or a proposed next task.

## Workflow

1. Read repository guidance and the supplied documents completely.
2. Inspect current repository evidence relevant to the documents.
3. Run two independent perspectives:
   - clarity: scope, terminology, internal consistency, acceptance criteria, and open decisions;
   - feasibility: repository fit, dependency order, verification, security, and operational constraints.
4. Reconcile both reviews with actual files. Label every conclusion as fact, inference, contradiction, or human decision.
5. Propose the smallest coherent corrections. Edit only when explicitly requested.
6. Re-review changed material once. A second correction pass is allowed only for blocking findings.
7. Stop when remaining issues require a product, legal, security, dependency, or priority decision.

Never invent requirements, priorities, paths, repository capabilities, or approvals. Do not copy product content into the harness. See [METHODOLOGY.md](METHODOLOGY.md) for the review contract.

## Output

Report inspected paths, evidence-backed findings, changes made, unresolved decisions, and the next bounded action. Distinguish completed, partial, and blocked work.
