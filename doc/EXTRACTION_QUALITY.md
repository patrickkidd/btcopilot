# Extraction quality watch list

Probabilistic LLM-output failures in PDP extraction. Each row: validator
branch detects, Ralph loop retries, repair helper runs as last-resort
safety net. Frequency columns updated by manual log grep until Datadog
is trusted.

## Currently watching

Pre-deploy baseline (2026-05-08) measured against `error.log` covering
2025-10-25 → 2026-05-08 (~196 days, ~6.5 months). Numbers are absolute hits
in that window. After deploy, compare against the same grep over a fresh
window to see whether the validator-then-Ralph promotion changes frequency.

| Issue | Validator branch | Repair helper | Warning grep | Last sampled freq | Status |
|---|---|---|---|---|---|
| Person self-parent | `validate_pdp_deltas` (added 2026-05-04) | `fix_self_parent_references` | `fix_self_parent_references:` | 0 hits / 196d (helper not yet deployed) | New |
| Birth event person==child | `validate_pdp_deltas` (added 2026-05-04) | `fix_birth_event_self_references` | `fix_birth_event_self_references:` | 6 hits / 196d (~1/mo) | Promoted |
| Duplicate pair-bond dyads | `validate_pdp_deltas` (existing) | `dedup_pair_bonds` | `dedup_pair_bonds:` | 5 hits / 196d (~1/mo) | Promoted |
| ID collisions | `validate_pdp_deltas` (existing) | `reassign_delta_ids` | `reassign_delta_ids:` | 7 hits / 196d (~1/mo) | Promoted |

Related Ralph-loop signals over the same window for context (NOT issue-specific):
- `PDP validation failed` (any retry attempt that failed): 40 hits
- `PDP extraction succeeded on retry`: 13 hits

## Adding a new issue

1. Add detection branch to `validate_pdp_deltas` (appends to `errors`).
2. Add `fix_xxx` helper near the others in `pdp.py`. Mutate in place. Log a
   warning naming the affected ids. Never fabricate clinical data.
3. Add invocation to the repair-on-exhaustion branch in `_extract_and_validate`.
4. Add unit tests for validator + helper, plus an integration test that drives
   the mocked LLM to exhaustion.
5. Add a row above.

## Sampling frequency (production)

Authorized SSH read-only per top-level CLAUDE.md. Run from any shell:

    ssh patrick@database.familydiagram.com 'grep -c "fix_self_parent_references:" /var/www/fdserver/instance/logs/error.log'
    ssh patrick@database.familydiagram.com 'grep -c "fix_birth_event_self_references:" /var/www/fdserver/instance/logs/error.log'
    ssh patrick@database.familydiagram.com 'grep -c "dedup_pair_bonds:" /var/www/fdserver/instance/logs/error.log'
    ssh patrick@database.familydiagram.com 'grep -c "reassign_delta_ids:" /var/www/fdserver/instance/logs/error.log'
    ssh patrick@database.familydiagram.com 'grep -c "PDP repair pass succeeded after retry exhaustion" /var/www/fdserver/instance/logs/error.log'

## Retiring an issue

Once a prompt-engineering change demonstrably drops frequency to near-zero
(logged in `PROMPT_ENGINEERING_LOG.md`), move the row to a "Resolved" section
below with date and link. Validator+repair stays as a safety net.
