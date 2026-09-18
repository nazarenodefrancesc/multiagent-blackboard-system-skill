# Blackboard Collaboration Skill

A controller-free Blackboard collaboration layer for heterogeneous AI agents sharing one Linux repository.

It is designed to sit on top of the **Scalable Ralph Loop Patch** memory model:

```text
PRD.md                     global routing context
prd/Txxx.md                canonical task specification
progress/PROGRESS-Txxx.md  bounded hot state
reports/                   cold evidence and proposal artifacts
Git                         provenance
```

and adds:

```text
.blackboard/claims/        task leases
.blackboard/notes/         weak shared signals
.blackboard/proposals/     proposal coordination metadata
.blackboard/events.jsonl   append-only audit
bb                          atomic coordination CLI
```

## Design goals

- no database;
- no message broker;
- no intelligent controller;
- Linux filesystem + `flock` + Git;
- single canonical writer per claimed macro-task;
- collaborative cold-start planning;
- notes that another agent can reinterpret/promote;
- consensus without a manager agent;
- complete provenance of who contributed what.

## Quick start

Requires Python 3.11+ on Linux. No runtime dependencies are required.

Run directly from the repository:

```bash
export BB_AGENT=hermes-01
./bin/bb init
./bin/bb status
```

Optional installation when desired:

```bash
python -m pip install .
bb status
```

Claim a task:

```bash
./bin/bb claim T003
./bin/bb heartbeat T003
# work, verify, update canonical task/progress
./bin/bb release T003
```

Leave a weak observation:

```bash
./bin/bb note --task T003 --type warning \
  "The external API appears rate-limited per API key."
```

Create and deliberate a proposal:

```bash
./bin/bb propose-task \
  --title "Database migrations" \
  --objective "Add deterministic schema migration support" \
  --priority P1

./bin/bb --agent prime-01 support P0001
./bin/bb --agent openclaw-01 support P0001
./bin/bb --agent reviewer-01 neutral P0001
./bin/bb --agent prime-01 consolidate P0001
```

The default consensus policy is 3 distinct non-author reviewers, 2 current supporters, and no unresolved hard objections.

Any proposal amendment creates a new revision and invalidates previous reviewer stances. For `NEW_TASK` proposals, use `bb amend-task` when title/objective/priority/dependencies/acceptance/verification change.

Accepted non-`NEW_TASK` proposals remain visible as pending canonical distillations until an agent incorporates the decision into `PRD.md` or `prd/Txxx.md` and records:

```bash
./bin/bb distill P0002 --into PRD.md
```

Open proposals can be explicitly retired with `bb withdraw`, or marked `SUPERSEDED` by an already accepted alternative.

## Repository layout

This repository is itself managed as a PRD-driven project. See `PRD.md`, `prd/`, `progress/`, and the included `.git` history in the distributed ZIP.

## MVP limitations intentionally left for pilot evidence

- claim ownership does not lock arbitrary source-code paths;
- agents share a working tree unless the host framework gives each agent its own worktree;
- no watcher wakes idle agents automatically;
- non-`NEW_TASK` accepted proposals are not semantically applied by `bb`; an agent edits canonical memory and `bb distill` records where that decision was incorporated;
- consensus thresholds are fixed defaults in this MVP.

These are explicit pilot targets, not hidden assumptions.
