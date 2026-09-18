# PROGRESS-T006 — Second-pass hardening and lifecycle correctness

## Current state

- Status: COMPLETE
- Completed: 2026-09-12
- Last update: 2026-09-12

## Outcome

Adversarial review and fine-tuning completed. Lifecycle correctness, proposal revision semantics, canonical distillation tracking, ID allocation, routing order, CLI ergonomics, human/machine state consistency, and provenance links were hardened without adding centralized intelligence.

## Verification

- Unit/regression suite: 23/23 PASS.
- Repository consistency: `bb check` PASS.
- End-to-end CLI information-loop smoke: PASS.
- Offline/no-dependency package install smoke: PASS.

## Sub-task status

| ID | Status | Evidence |
|---|---|---|
| T006-SUB001 | COMPLETE | [REPORT-T006-SUB001](../reports/REPORT-T006-SUB001.md) |
| T006-SUB002 | COMPLETE | Regression suite + implementation commit |
| T006-SUB003 | COMPLETE | CLI/core regression suite + integration smoke |
| T006-SUB004 | COMPLETE | [REPORT-T006-SUB004](../reports/REPORT-T006-SUB004.md) |

## Important final decisions

- Proposal amendments create new revisions and require fresh reviewer stances.
- `NEW_TASK` material changes use structured `amend-task` updates.
- Accepted non-task decisions remain visibly pending until `bb distill` records canonical incorporation.
- Stale ID counters self-heal against observed stable IDs.
- Source-file locking, semantic proposal dedupe, and wake-up watchers remain deferred to pilot evidence.

## Relevant reports

- [Adversarial second-pass findings](../reports/REPORT-T006-SUB001.md)
- [v0.1.1 verification and packaging readiness](../reports/REPORT-T006-SUB004.md)

## Remaining follow-up

- Run Pilot 0 and record protocol failures in `PILOT_ISSUES.md` before adding further coordination mechanisms.
