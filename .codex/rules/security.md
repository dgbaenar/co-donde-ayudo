# Security rule

## Scope

Apply this rule whenever work can touch credentials, configuration, private data, authentication,
external systems, logs, examples, or generated artifacts.

## Required behavior

- Keep secrets server-side, configuration-driven, and outside tracked files.
- Use synthetic data in tests, examples, screenshots, logs, and reports.
- Minimize access to private data and inspect only the metadata or structure needed for the task.
- Treat authentication, authorization, input validation, output encoding, and failure handling as
  explicit behavior with tests when they are in scope.
- Report a security failure or missing control plainly; stop when continuing would expose data or
  mutate a real system.

## Approval boundaries

Require explicit user approval before reading private data, writing to an external system, using
real infrastructure, invoking a paid service, or changing security-sensitive configuration.

## Prohibited shortcuts

- Never read, print, log, expose, copy, or commit credentials or real environment-file contents.
- Never hard-code a secret, disable a security control, silently downgrade behavior, or use
  production data as a convenient fixture.
- Do not send repository or user data to an unapproved external service.
- Do not represent the absence of an error as evidence that a security property holds.
