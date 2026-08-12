# Documentation rule

## Scope

Apply this rule to repository guidance, specifications, plans, backlogs, architecture notes,
handoffs, examples, and user-facing development documentation.

## Required behavior

- Maintain one source of truth per topic and link to it instead of duplicating large passages.
- Use real repository-relative paths, configured commands, current terminology, and verified status.
- Update documentation in the same approved task as the behavior or interface it describes.
- Distinguish implemented state, planned work, assumptions, decisions, and unresolved blockers.
- Keep reusable harness instructions independent of application requirements; consume supplied
  specifications at task time.

## Approval boundaries

Obtain explicit user approval before changing the meaning or scope of an authoritative
specification, recording an unconfirmed decision as final, or publishing documentation externally.

## Prohibited shortcuts

- Do not copy application requirements into reusable harness rules or skills.
- Do not invent paths, commands, test results, decisions, dates, owners, or implementation status.
- Do not duplicate an authoritative document to make a competing source of truth.
- Do not leave documentation claiming behavior that current repository evidence contradicts.
