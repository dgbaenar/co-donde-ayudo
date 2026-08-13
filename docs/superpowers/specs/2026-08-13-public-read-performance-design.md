# Public read performance design

## Goal

Make the public home and help-point detail pages display useful information quickly while keeping
the full set of active points available and accepting up to five minutes of staleness.

## Verified problem

Production measurements on 2026-08-13 showed approximately 9.8 seconds to first byte for the home
page and 8.8 seconds for one detail page, while `/healthz` answered in about 0.4 seconds. The detail
service currently loads every active point and then searches for one UUID in Python.

## Design

- Keep one runtime-owned, in-process public-data cache with a 300-second TTL. Do not add Redis or a
  dependency.
- Serve fresh cached data immediately. When cached data is stale, serve it immediately and refresh
  it in the background. Preserve the last successful value when refresh fails.
- On a cold home cache, render the shell immediately, load the newest 24 points, and continue
  automatically until every active point is visible. Append each batch without clearing and
  rebuilding all existing cards or the complete map.
- Bound database waits so the loading state cannot remain indefinitely. Show an actionable status
  when no cached data exists and the database cannot be reached.
- Resolve a detail route with a direct active-row query by UUID and eager-load only that point's
  required relationships. Reuse a cached point when available.
- Keep filters disabled while the cold result is incomplete. Cached complete results remain fully
  interactive while a background refresh runs.

## Consistency and failure behavior

The cache may be up to five minutes old by product decision. Successful writes and refreshes update
or invalidate affected cached values. A failed refresh never removes a previously usable public
snapshot. A cold failure shows an error rather than an endless spinner.

## Verification

- Unit tests cover TTL boundaries, stale reads, failed refresh retention, direct UUID lookup, and
  progressive completion.
- Frontend tests prove every batch becomes visible, controls are honest, and timeout/failure states
  terminate loading.
- The full local suite must pass. Production latency must be measured again after deployment; local
  tests cannot prove Railway/Supabase response time.
