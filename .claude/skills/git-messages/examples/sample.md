# Example Output

This is a concrete example of what the skill produces. The diff inspected was a change
that fixes a point-in-time bug where `available_at` was derived from
`first_observed_at` alone instead of the latest of all three candidate timestamps.

---

## Inspection output (summarised)

```
Branch: dgbaenar/fix-pit-available-at-derivation
Modified: src/investment_agents/domain/pit.py
Modified: tests/test_pit_envelope.py
```

---

## Branch name

```
dgbaenar/fix-pit-available-at-derivation
```

---

## Commit message

```
fix(domain): derive available_at from the latest candidate timestamp

available_at was computed from first_observed_at and ingested_at only,
silently ignoring normalization_completed_at when it was the later of
the three. A record whose normalization finished after ingestion could
be treated as available (and PIT-eligible) earlier than it actually
was — a lookahead risk into every downstream cutoff assessment.

available_at is now the max of first_observed_at, ingested_at, and
normalization_completed_at (when present), matching the point-in-time
contract every envelope must satisfy.
```

---

## PR title

```
fix(domain): derive available_at from the latest candidate timestamp
```

---

## PR description

```markdown
## Summary

`PITEnvelope.available_at` was derived from `first_observed_at` and
`ingested_at` only, ignoring `normalization_completed_at` even when it was
the later timestamp. This let a record be treated as point-in-time eligible
before normalization had actually finished — a lookahead risk that
`methodological-integrity.md` exists to catch.

## Changes

- `_validate_envelope` now includes `normalization_completed_at` (when
  present) among the candidates used to derive `available_at`
- Regression test added with a synthetic envelope where
  `normalization_completed_at` postdates `ingested_at`, asserting
  `available_at` reflects the later timestamp

## Test plan

- [ ] `uv run pytest -q tests/test_pit_envelope.py` passes
- [ ] Regression test fails against the pre-fix implementation (verified by
  reverting the fix locally and re-running)
```
