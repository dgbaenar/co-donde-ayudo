# Delegation rule

## Scope

Apply this rule whenever work is assigned to a subagent or split across agents.

## Required behavior

- The main agent retains responsibility for scope, decisions, approval boundaries, coordination,
  final integration, and user communication.
- Give each implementer one approved task with explicit paths, acceptance criteria, constraints,
  and required evidence.
- Route backend implementation to `backend_developer`, frontend implementation to
  `frontend_developer`, read-only checks to `local_verifier`, structural review to
  `python_architect`, supplied-document review to `document_reviewer`, and independent evidence and
  scope review to `integrity_auditor`.
- Use an independent agent for verification or review after implementation.
- Fan out only tasks with no shared write surface or sequential dependency. Reconcile all findings,
  then inspect changed files and rerun decisive checks in the main agent.

## Approval boundaries

Obtain explicit user approval whenever delegated work would cross the dependency, Git, external
system, private-data, paid-service, or task-scope boundaries defined by repository guidance.
Delegation does not expand authority.

## Prohibited shortcuts

- Do not assign overlapping writes concurrently or delegate an unresolved product decision.
- Do not let a subagent broaden scope, change dependencies, mutate Git, or contact an external
  system without the required user approval.
- Do not accept a subagent's success report as proof or conceal unresolved review findings.
- Do not claim independent review when the implementer reviewed only its own work.
