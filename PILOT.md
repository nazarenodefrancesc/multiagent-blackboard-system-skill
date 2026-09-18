# Pilot 0 — Blackboard Collaboration

## Goal

Use the first real multi-agent run to discover coordination and information-flow failures, not to prove the architecture correct.

## Setup

- 4 heterogeneous agents first; scale to 6–7 only after the first postmortem.
- Same Linux machine and shared repository.
- Same brief delivered to all agents.
- Same `SKILL.md` available to all agents.
- No assigned roles.
- No intelligent controller.
- Start from brief + root PRD with an empty Blackboard task index.

## Suggested software brief

Build a small shared task-management web application with:

- HTTP API;
- browser UI;
- persistence;
- multi-user behavior;
- automated tests;
- logging;
- Docker packaging;
- concise documentation.

Keep the product small enough to finish but broad enough to create architecture, API, data, frontend, test, integration, and deployment decisions.

## What to observe

### Cold start

Look for:

- duplicate decompositions/proposals;
- agents implementing before canonical tasks exist;
- agents reading and amending existing proposals instead of restarting planning independently;
- stalled proposals that nobody revisits.

### Execution

Look for:

- claim contention and recovery;
- writes to another agent's canonical `Txxx + PROGRESS` pair;
- shared source-file collisions;
- accidental commits of unrelated working-tree changes;
- expired claim takeover quality.

### Information loops

Look specifically for cross-agent chains such as:

```text
Hermes note → Prime proposal → OpenClaw implementation
```

Track:

- notes later consumed by another agent;
- notes that become dead ends;
- proposals created from other agents' observations;
- reviews that trigger fixes;
- discoveries during execution that become new Txxx tasks.

### Deliberation

Look for:

- proposal explosion;
- meaningless SUPPORT just to pass the threshold;
- abuse of HARD_OBJECTION for preferences;
- deadlock after a legitimate hard objection;
- whether amendment-driven fresh reviews create excessive friction;
- proposals that should be withdrawn/superseded but remain open;
- accepted non-task decisions that remain pending canonical distillation too long.

## Deliberate perturbations

1. Kill one agent while it owns a task. Verify lease expiry, takeover, and recovery from Progress/current working tree.
2. Include an ambiguous requirement likely to produce a weak note rather than an immediate proposal.
3. Omit one operational requirement so execution should discover it and create a new canonical task through the proposal loop.

## Minimal measurements

- duplicate proposals/tasks;
- claim conflicts;
- expired-claim recoveries;
- notes created / notes consumed;
- cross-agent note consumption;
- proposals accepted / withdrawn / superseded / stuck;
- accepted proposals pending canonical distillation;
- hard objections created / resolved;
- cross-agent reviews;
- new tasks discovered during execution;
- human interventions required;
- source-file conflicts;
- events for which provenance cannot be reconstructed.

## Primary qualitative metric

A Blackboard is genuinely collaborative when useful information crosses agent boundaries.

The key signal is not total output but **cross-agent contribution chains**:

```text
Agent A discovers → Agent B interprets → Agent C acts
```

If most chains remain `A → A → A`, the system is behaving more like independent agents sharing storage than a collaborative Blackboard.

## During the run

Do not patch every odd behavior immediately. Record pilot issues separately and finish the run unless safety/data corruption requires intervention.

Suggested issue file:

```text
PILOT_ISSUES.md
```

Examples:

```text
I001 — Duplicate proposals despite existing equivalent proposal
I002 — Unconsumed notes never revisited
I003 — Agent modifies another owner's Progress
I004 — Shared source file overwritten by second task owner
I005 — Proposal remains stuck after challenge
```

## Exit condition

End the pilot when the app is operational, required tests pass, canonical tasks are complete, and there are no unresolved critical blockers/hard objections. Then analyze the event log and Git history before changing the protocol.
