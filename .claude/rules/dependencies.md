# Dependency rule

## Scope

Apply this rule to Python packages, developer tooling, runtimes, lockfiles, registries, downloaded
executables, and commands that can resolve or install software.

## Required behavior

- Use Python `>=3.12` and declare the supported range in `pyproject.toml` when initializing a Python
  project.
- Use `uv` exclusively for Python project metadata, environments, dependency resolution, locking,
  and approved command execution.
- Prefer the standard library and existing declared dependencies when they satisfy the current
  requirement.
- Before proposing a dependency change, identify the exact version, release age, purpose, runtime
  or development scope, lockfile impact, compatibility constraints, and important transitive risks.
- After an approved change, inspect the manifest and lockfile and run relevant configured checks.

## Approval boundaries

Require explicit user approval before adding, removing, updating, resolving, locking, downloading,
or installing dependencies or toolchains. The approval must cover the stated package and command.

## Prohibited shortcuts

- Do not run an installer, resolver, lock update, or environment synchronization before approval.
- Do not use ad-hoc installers, unverified URLs, unofficial registries, floating versions, or an
  alternative Python package manager.
- Do not add a package to avoid a small standard-library implementation without a current need.
- Do not conceal transitive changes or edit a lockfile by hand.
