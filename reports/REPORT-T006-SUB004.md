# REPORT-T006-SUB004 — v0.1.1 verification and packaging readiness

## Related specification

- [T006](../prd/T006.md)
- Sub-task: T006-SUB004

## Purpose

Verify the hardened Blackboard MVP after the adversarial second pass and confirm that Pilot 0 can start from a consistent, installable, provenance-preserving repository.

## Verification performed

### Unit/regression suite

Command:

```bash
python -m unittest discover -s tests -v
```

Result:

```text
23 tests passed
```

Coverage includes:

- dependency-aware task availability;
- IN_PROGRESS routing precedence;
- exclusive claim contention and lease takeover;
- canonical-state validation on claim/complete;
- note reply/search/consumption;
- note → proposal promotion;
- consensus thresholds and hard objections;
- proposal revision invalidating stale stances;
- structured `NEW_TASK` revision and materialization;
- proposal withdrawal and supersession;
- accepted non-task proposal distillation;
- task-scoped distillation ownership/scope checks;
- ID-counter self-healing;
- human/machine status consistency;
- `--agent` accepted both before and after subcommands.

### Repository consistency

Command:

```bash
./bin/bb check
```

Result:

```text
Blackboard consistency: PASS
```

### End-to-end CLI smoke

A fresh temporary project was initialized and exercised through this chain:

```text
brief
→ note
→ NEW_TASK proposal
→ review
→ structured amendment
→ stale consensus correctly rejected
→ fresh review
→ consolidation
→ T001 materialization
→ claim
→ canonical COMPLETE
→ claim completion
→ generic accepted proposal
→ pending canonical distillation
→ PRD distillation
→ proposal withdrawal
→ bb check PASS
```

This smoke used `--agent` after the subcommand to verify the literal skill syntax.

### Installability

Command:

```bash
python -m pip install . --target <temp-dir> --no-deps --no-build-isolation
```

Result:

```text
installed-package-smoke: PASS
version: 0.1.1
```

The direct repository launcher `bin/bb` remains dependency-free at runtime.

## Important fixes since v0.1.0

- proposal revisions invalidate stale reviewer stances;
- structured `NEW_TASK` amendments update materialization state;
- open proposals can be withdrawn or superseded;
- non-task accepted decisions expose pending canonical distillation until closed;
- task-scoped distillation requires the caller's live claim and correct task target;
- note/proposal Markdown status stays synchronized with machine state;
- ID allocation self-heals stale persisted counters;
- `IN_PROGRESS` work is routed before new `PLANNED` work;
- proposal provenance links remain valid after title revisions;
- completion events no longer misattribute repository HEAD as the agent's commit;
- `bb check` validates more human/machine state invariants;
- documented `--agent` placement now works literally.

## Deliberately unchanged for Pilot 0

- source-code path conflicts are not locked;
- all agents may still share one working tree;
- there is no semantic duplicate-proposal detector;
- there is no watcher that wakes idle agents;
- consensus thresholds remain fixed at 3 reviewers / 2 support / 0 unresolved hard objections.

These remain observation targets rather than pre-emptive architecture additions.

## Conclusion

v0.1.1 is ready for Pilot 0. The second pass materially strengthened information-loop correctness without adding a controller, database, broker, or semantic decision engine.
