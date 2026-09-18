# Blackboard Collaboration Skill — PRD

## Project description

Implement a lightweight, controller-free Blackboard collaboration layer for heterogeneous agents sharing one Linux repository. The system extends the Scalable Ralph memory model with distributed collaboration primitives while preserving Markdown + Git as the canonical project memory.

## Objective

Deliver an installable agent skill plus a dependency-free `bb` CLI that lets multiple agents coordinate through a shared filesystem using claims, notes, proposals, consensus, task materialization, provenance, and an append-only event log.

## Global scope

In scope:

- framework-agnostic `SKILL.md` for OpenClaw, Hermes, Prime Agent, and similar agents;
- single-writer claims over `prd/Txxx.md` + `progress/PROGRESS-Txxx.md`;
- Linux `flock`-backed atomic mutations;
- unstructured shared notes and note promotion;
- proposals, support/challenge/hard-objection, mechanical consensus validation, and consolidation;
- automatic materialization of accepted `NEW_TASK` proposals;
- Git-aware audit/provenance helpers;
- no database and no intelligent controller;
- tests suitable for a first multi-agent pilot.

Out of scope for MVP:

- semantic ranking/routing of agents;
- message brokers or server processes;
- vector databases;
- automatic quality judgment of proposals;
- automatic agent wake-up/watchers;
- hard isolation of source-code files between concurrent agents;
- distributed/multi-host coordination.

## Global constraints and invariants

- The Blackboard must remain filesystem + Git based.
- `bb` may enforce mechanics but must not make semantic product or architecture decisions.
- A claim on `Txxx` grants exclusive canonical write ownership over both `prd/Txxx.md` and `progress/PROGRESS-Txxx.md` for the lease duration.
- All agents may read canonical task state and may contribute non-canonical notes/reports while another agent owns the task.
- `flock` is used only for short atomic mutations, never for the duration of agent reasoning/work.
- Notes are weak signals; proposals request canonical change; accepted decisions are distilled into canonical PRD/task state.
- Event history is append-only and distinct from current canonical state.
- Proposal consolidation uses formal thresholds only; `bb` never judges whether a proposal is semantically good.
- New canonical tasks are created only by consolidating accepted `NEW_TASK` proposals.
- Agents are allowed to abstain/idle when they cannot add material value.
- Stable IDs are never reused.

## Consensus policy

Default MVP thresholds:

- at least 3 distinct reviewers other than the proposal author;
- at least 2 current `SUPPORT` stances from reviewers;
- zero unresolved `HARD_OBJECTION` records.

`CHALLENGE` is non-blocking. A hard objection remains blocking until its author resolves it.

## Macro-task index

<!-- BB:TASK_INDEX:START -->
| ID | Macro-task | Status | Priority | Dependencies | Specification | Progress |
|---|---|---|---|---|---|---|
| T001 | Collaboration contract and skill | COMPLETE | P0 | — | [T001](prd/T001.md) | [PROGRESS-T001](progress/PROGRESS-T001.md) |
| T002 | Filesystem coordination and claims | COMPLETE | P0 | T001 | [T002](prd/T002.md) | [PROGRESS-T002](progress/PROGRESS-T002.md) |
| T003 | Notes, proposals, and consensus loops | COMPLETE | P0 | T002 | [T003](prd/T003.md) | [PROGRESS-T003](progress/PROGRESS-T003.md) |
| T004 | Task materialization, audit, and provenance | COMPLETE | P1 | T003 | [T004](prd/T004.md) | [PROGRESS-T004](progress/PROGRESS-T004.md) |
| T005 | Verification and pilot readiness | COMPLETE | P0 | T004 | [T005](prd/T005.md) | [PROGRESS-T005](progress/PROGRESS-T005.md) |
| T006 | Second-pass hardening and lifecycle correctness | COMPLETE | P0 | T005 | [T006](prd/T006.md) | [PROGRESS-T006](progress/PROGRESS-T006.md) |
<!-- BB:TASK_INDEX:END -->

## High-level dependencies

`T001 -> T002 -> T003 -> T004 -> T005 -> T006`

## Global open questions

- Whether source-code path ownership/file leases are needed after observing the first pilot.
- Whether the consensus thresholds should remain fixed or become project-configurable after pilot evidence.
- Whether a future watcher should wake idle agents on Blackboard changes without gaining decision authority.
