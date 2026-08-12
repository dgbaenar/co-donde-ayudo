# Review methodology

## Perspective A: document quality

Check purpose, scope boundaries, actor-neutral terminology, flows, failure states, privacy constraints, binary acceptance criteria, dependency order, and unresolved choices.

## Perspective B: repository feasibility

Check the current tree, implemented interfaces, tests, configuration, dependency declarations, deployment evidence, and conflicts with repository guidance.

## Reconciliation

Prefer direct file evidence over assumptions. A document may describe intended state; label it as intended until code or configuration proves it exists. Never silently resolve a decision whose alternatives materially change scope, data handling, architecture, cost, or external behavior.

## Completion gate

Complete only when both perspectives have been reconciled, blocking contradictions are resolved or surfaced, edits were independently re-read, and the next action has explicit scope and binary acceptance criteria.
