# REPORT-T005-SUB001 — Verification report

## Related specification

- [T005](../prd/T005.md)
- Sub-task: T005-SUB001

## Purpose

Verify the critical mechanical contracts of the Blackboard Collaboration MVP before the first heterogeneous multi-agent pilot.

## Context and inputs

Implementation under test:

- Linux `fcntl.flock` coordination;
- PRD task routing and dependency readiness;
- claim/lease/heartbeat/release/complete lifecycle;
- notes, replies, search, consumption, and promotion;
- proposals, latest stances, hard objections, resolution, and consensus readiness;
- accepted `NEW_TASK` materialization;
- history/contribution queries and consistency checking.

## Work performed

Automated test suite exercises:

1. task availability and dependency readiness;
2. claim exclusivity and ownership;
3. rejection of claims with unmet dependencies;
4. completion as validation rather than semantic decision;
5. two-process concurrent claim contention;
6. expired-claim takeover;
7. note reply/search/consumption;
8. note-to-proposal promotion;
9. proposal-author exclusion from reviewer counts;
10. latest-stance semantics;
11. blocking hard objection and author-only resolution;
12. rejection of premature consolidation;
13. deterministic new-task materialization and provenance;
14. consistency mismatch detection and per-agent contribution audit.

## Findings

Two implementation defects were found and fixed before the final suite:

- `bb init` attempted to pass a `root` event field that collided with the function's `root` argument. The event field was renamed to `project_root`.
- initial stable task-counter inference looked only at `prd/Txxx.md`; this could reuse an ID present in the root PRD index if its task file had not yet been created. Counter bootstrap now also scans task identifiers in `PRD.md`.

The pilot should still treat source-code working-tree concurrency and coordination-metadata Git noise as open empirical questions.

## Verification

- Command: `python -m unittest discover -s tests -v`
- Result: PASS, 13 tests.
- Additional command: `./bin/bb check`
- Result before final packaging: PASS.
- Direct repository launcher from a nested working directory: PASS.
- Offline package install to an isolated target using local build tooling: PASS.

## Decision

Mechanical implementation is suitable for Pilot 0.

## Remaining issues

- No source-file ownership beyond macro-task canonical state.
- No automatic wake-up mechanism.
- No semantic duplicate-proposal detection.
- Consensus thresholds are fixed defaults for the MVP.

## Follow-up

Run Pilot 0 using `PILOT.md`, capture issues in `PILOT_ISSUES.md`, and change the protocol only after the postmortem unless a run-time issue threatens repository integrity.
