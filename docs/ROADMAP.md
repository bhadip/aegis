# ROADMAP (living tracker - read this first in any new session)

## Automated, no human action needed
- Analytics reports self-gate on data sufficiency (50 scans / 100 aged pairs). They appear in the Analytics tab automatically once thresholds are met.

## Open human decisions (review when data suffices)
1. After >= 30 days of accuracy data: review bias hit-rates and score-return correlations.
   If |corr(score, 4h return)| < 0.2 or hit-rates < 55%, recalibrate: consider blending price momentum into Risk Score, or re-weighting grid/TP risk factors. Record decision in CHANGELOG.
2. Optional (user-requested only): fixed 24h scoring window for day-over-day comparability.
3. Optional (deferred, rejected for now): historical backfill mode - would simulate sentiment on cached headlines; ground-truth logging preferred.

## Conventions
- Versioning: major only on explicit user request; minor for new functionality; patch for bugfixes.
- Git pushes only on explicit user request, and always as Block 1 of the reply.
- Files > 50 lines delivered via single-block Python generators; one uninterrupted block per file.
