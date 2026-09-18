---
name: blackboard-collaboration
version: 0.1.1
description: "Controller-free Blackboard collaboration skill for heterogeneous agents sharing a Scalable Ralph-style Markdown + Git repository. Use for multi-agent planning, execution, review, discovery, notes, proposals, consensus, task claims, and provenance."
---

# Blackboard Collaboration

## Purpose

Use this skill when multiple independent agents collaborate on the same project repository through shared state rather than direct orchestration.

This skill **extends** the Scalable Ralph memory model. It does not replace the PRD Context Router or redefine its authority model.

The core architecture is:

```text
agents
  ↕
shared Blackboard
  ↕
bb CLI
  ↕
filesystem + flock + Git
```

There is **no intelligent controller**. Agents make semantic decisions. `bb` provides only atomic coordination, validation, IDs, and audit.

---

## Core principle

Collaboration is not primarily agent-to-agent messaging.

It is a repeated loop in which agents observe, enrich, and react to a shared representation of the problem:

```text
READ → ORIENT → CONTRIBUTE → UPDATE → RE-READ
```

Do not behave as:

```text
READ → EXECUTE ONCE → EXIT
```

A contribution may be partial. One agent may discover a fact, another may interpret it, and a third may implement the consequence.

---

## Information model

Treat project information as layers with different maturity and authority.

```text
PRD.md / prd/Txxx.md
    CANONICAL SPECIFICATION
    accepted project/task truth

progress/PROGRESS-Txxx.md
    CANONICAL HOT STATE
    current execution state

current implementation
    PRESENT REALITY
    code, tests, artifacts, working tree

reports/
    COLD STRUCTURED EVIDENCE
    investigations, reviews, proposal artifacts

.blackboard/notes/
    WEAK SHARED SIGNALS
    observations, ideas, warnings, questions, pointers

.blackboard/proposals/
    MACHINE COORDINATION METADATA
    current proposal stances/objections; human proposal body remains in reports/

.blackboard/events.jsonl
    APPEND-ONLY AUDIT
    how the system evolved

Git history
    HISTORICAL PROVENANCE
    commits, diffs, reversals, authorship
```

### Authority

Current desired state is determined by current PRD/task specifications, Progress, and implementation.

Notes, reports, proposals, events, and old Git history must not silently override canonical current state.

### Maturity ladder

Use the least formal artifact that correctly represents the information:

```text
weak signal              → NOTE
structured investigation → REPORT
request for canonical change → PROPOSAL
accepted work            → Txxx
current execution        → PROGRESS
accepted truth           → PRD / task specification
```

Do not over-formalize every thought into a proposal.

---

## Startup procedure

When entering a Blackboard project:

1. Read repository instructions (`AGENTS.md`, `CLAUDE.md`, etc.) if present.
2. Read `PRD.md`.
3. Inspect `git status --short`.
4. Run `bb status`.
5. If you already own a live claim, resume that task first unless blocked.
6. Otherwise inspect useful work using the information-loop priority below.
7. Load only the active task specification, Progress, relevant implementation, and relevant cold evidence.
8. Do not read the entire project history by default.

Never overwrite unrelated working-tree changes. In a shared working tree, stage and commit only paths belonging to your contribution; do not use `git add -A` blindly.

---

## Information-loop priority

When deciding what to do next, use this order as a default, not a rigid business workflow:

1. Resume your own live claimed task if useful work remains.
2. Help resolve a concrete blocker you can materially unblock.
3. Close an accepted proposal with pending canonical distillation when you can safely apply it.
4. Claim an executable available task you can advance.
5. Review an open proposal when your review can change confidence or resolve uncertainty.
6. Inspect unconsumed notes you can deepen, connect, or promote.
7. Review a meaningful artifact/task where cross-agent inspection adds value.
8. Deposit a new note if you observed useful information not yet represented.
9. If nothing material can be added, become idle.

During cold start, when no executable canonical tasks exist, prioritize discovery and proposals over implementation.

Agents are **not required to contribute** merely because they were activated.

---

## Cold-start loop

If the PRD contains no executable tasks or the brief is not yet decomposed:

```text
brief
  ↓
agents observe independently
  ↓
notes / reports / proposals
  ↓
read existing contributions before duplicating them
  ↓
support / challenge / hard objection / amendment
  ↓
consolidation
  ↓
canonical Txxx tasks
  ↓
execution
```

Rules:

- Do not implement substantial work before canonical executable tasks exist.
- Before creating a new proposal, inspect open proposals for semantic overlap.
- Prefer supporting, challenging, or amending an existing proposal over creating a duplicate.
- A proposal is not a task. A canonical task exists only after consolidation.

---

## Claim semantics

Before editing canonical task state, claim the macro-task:

```bash
bb claim T003 --agent "$BB_AGENT"
```

A live claim on `T003` grants exclusive **canonical write ownership** over both:

```text
prd/T003.md
progress/PROGRESS-T003.md
```

All agents may still read those files.

Non-owners may still contribute through:

- notes;
- reports/reviews;
- proposal artifacts;
- independent artifacts that do not overwrite the owner’s canonical state.

### Claim vs flock

A claim is a long logical lease:

```text
Hermes owns T003 for N minutes
```

`flock` is a short physical mutex used only while `bb` performs an atomic filesystem mutation.

Never hold `flock` while reasoning, coding, testing, or waiting on a model.

### Lease lifecycle

Use:

```bash
bb heartbeat T003
bb release T003
bb complete T003
```

Renew a claim while actively working. If an agent dies, the lease expires and another agent may reclaim the task.

Before takeover after expiry, read `PROGRESS-T003.md`, current implementation, and `git status --short` to reconstruct present reality.

### Source-code concurrency

The MVP claim protects the canonical task specification and Progress pair, not arbitrary source-code paths.

Therefore:

- inspect `git status --short` before edits and commits;
- avoid modifying files another active task is visibly changing when possible;
- stage only your own paths;
- record conflicts as notes/blockers rather than silently overwriting work.

Do not invent source-file locks unless the project owner extends the protocol.

---

## Execution loop

For an executable task:

```text
READ STATE
  ↓
CLAIM Txxx
  ↓
load focused context
  ↓
WORK
  ↓
VERIFY
  ↓
update implementation + PROGRESS
  ↓
commit scoped changes
  ↓
COMPLETE or RELEASE
  ↓
RE-READ BLACKBOARD
```

Completing one task does not automatically end your iteration. Re-read the Blackboard once to see whether your work unblocked another task, created a review opportunity, or changed the usefulness of existing notes/proposals.

Do not remain active when there is no material next contribution.

---

## Notes: weak shared signals

Use a note when information may be useful but is not yet mature enough to justify a canonical change.

Examples:

- observation;
- warning;
- idea;
- question;
- useful pointer/link;
- possible inconsistency;
- partial research result.

Create one with:

```bash
bb note --type observation --task T003 "External API appears limited to 100 req/min."
```

Notes are Blackboard deposits, not direct messages.

Prefer:

```text
"Current shutdown path may race with worker cleanup."
```

over:

```text
"Hey Prime, can you check this?"
```

### Replies

A reply is allowed when it adds evidence or interpretation:

```bash
bb reply N0042 "Confirmed against the provider docs; the limit is per API key."
```

Do not turn note threads into open-ended chat.

### Note consumption

A note is `OPEN` until its information has been incorporated into another artifact/state.

Examples:

```text
N0048 → consumed_by P0017
N0052 → consumed_by T006
N0061 → consumed_by REPORT-T004-SUB002
```

`CONSUMED` means "handled/incorporated", not "true".

Inspect unresolved weak signals with:

```bash
bb notes --unconsumed
```

### Promotion

Another agent may promote a note into a proposal:

```bash
bb propose --from-note N0048 ...
```

This cross-agent reinterpretation is a desired Blackboard behavior.

---

## Reports

Use `reports/` for structured evidence that is too deep for Progress and too mature for a raw note.

Typical report roles:

- investigation;
- design comparison;
- benchmark;
- review;
- failure analysis;
- verification evidence.

Reports do not silently become canonical requirements.

If a report implies canonical change, create/update a proposal and later distill the accepted outcome into the correct PRD/task specification.

---

## Proposals

A proposal means:

> "I propose that the shared canonical state/work should change in this way."

The human-readable proposal is stored under `reports/`; current machine coordination state is stored under `.blackboard/proposals/`.

Use proposals for:

- new canonical task;
- requirement/scope change;
- architecture change;
- dependency change;
- acceptance-criteria change;
- project-wide or task-wide decision that future work must obey.

Do not use a proposal for routine implementation steps already inside the claimed task scope.

### Deliberation actions

Reviewers may express:

```text
SUPPORT
NEUTRAL
CHALLENGE
HARD_OBJECTION
```

`CHALLENGE` is non-blocking and means the proposal needs clarification or improvement.

`HARD_OBJECTION` is blocking and must identify a concrete reason such as:

- violated requirement;
- incompatibility;
- correctness error;
- critical unresolved risk;
- missing dependency;
- contradiction with canonical state.

A preference alone is not a hard objection.

### Amendments

Amendments append clarification or revised proposal content while preserving history. Do not erase the original proposal history merely to make consensus easier.

Every amendment creates a new proposal revision. **Reviewer stances from previous revisions no longer count toward consensus.** Reviewers must explicitly re-record their stance on the current revision.

For a `NEW_TASK` proposal, use a structured revision whenever the materialized task definition changes:

```bash
bb amend-task P0017 \
  --objective "Revised objective" \
  --priority P1 \
  --acceptance "Observable acceptance criterion" \
  --verification "Verification command/probe"
```

Use `--clear-depends` when a revision intentionally removes all macro-task dependencies.

Use plain `bb amend` only for proposal text/clarification that does not need a different structured `NEW_TASK` payload.

### Proposal retirement

Not every proposal should remain open forever.

The proposal author may withdraw an open proposal:

```bash
bb withdraw P0017 --reason "Evidence no longer supports this approach"
```

If an alternative proposal has already been accepted, any agent may record that an overlapping open proposal is superseded:

```bash
bb supersede P0017 --by P0021 --reason "P0021 is the accepted replacement"
```

`WITHDRAWN` and `SUPERSEDED` preserve the full deliberation history; they do not erase the proposal.

---

## Consensus and consolidation

The MVP uses **operational consensus**, not unanimity.

Default formal threshold:

```text
reviewers >= 3 distinct non-author agents
current SUPPORT >= 2 non-author agents
unresolved HARD_OBJECTION == 0
```

The proposal author does not count as a reviewer.
Only stances recorded against the **current proposal revision** count.

Any agent may attempt:

```bash
bb consolidate P0017
```

`bb` does not judge the proposal. It only verifies the formal policy atomically.

If conditions fail, deliberation continues.

If conditions pass:

- proposal status becomes `ACCEPTED`;
- an audit event is appended;
- a `NEW_TASK` proposal is materialized as the next stable `Txxx` and inserted into the root task index;
- other proposal kinds become `ACCEPTED` with `distillation_status=PENDING` until the accepted decision is explicitly incorporated into canonical memory.

Do not leave an accepted active requirement discoverable only in an old report.

For a non-`NEW_TASK` proposal:

1. edit the correct canonical `PRD.md` or `prd/Txxx.md` with the distilled current truth;
2. if editing `prd/Txxx.md`, first hold the live claim for that task;
3. then close the loop mechanically:

```bash
bb distill P0017 --into prd/T003.md \
  --note "Accepted auth rule distilled into task contract"
```

For global decisions:

```bash
bb distill P0017 --into PRD.md
```

`bb distill` does not judge whether the text is semantically correct and does not edit it for you. It records the agent's attestation and provenance of where the accepted decision was consolidated.

---

## New-task rule

A new canonical task may be created only by consolidation of a `NEW_TASK` proposal.

Use:

```bash
bb propose-task --title "Database migrations" \
  --objective "Add deterministic schema migration support" \
  --priority P1
```

After consensus:

```bash
bb consolidate P0017
```

mechanically allocates the next never-reused `Txxx`, creates:

```text
prd/Txxx.md
progress/PROGRESS-Txxx.md
```

and updates the marked task index in `PRD.md`.

Routine sub-work inside an existing task does not require a new proposal/task.

---

## Review loop

Non-owners should review through evidence artifacts rather than modifying another owner’s canonical state.

```text
artifact/task
  ↓
independent review
  ↓
report / note / proposal
  ↓
owner reads contribution
  ↓
fix / clarification
  ↓
verification
  ↓
updated canonical state
```

A good review may be a high-value contribution even if the reviewer writes no production code.

---

## Blocker loop

A blocker belongs in current Progress when it prevents execution.

Other agents may observe it and opportunistically solve the prerequisite.

```text
T004 blocked
  ↓
shared Progress exposes blocker
  ↓
another agent notices
  ↓
relevant work / proposal / note
  ↓
blocker resolved
  ↓
T004 proceeds
```

Do not require direct agent-to-agent messaging for blocker propagation.

---

## Idle loop

If no task is immediately claimable, do not fabricate work.

Check:

```text
open blockers I can resolve?
accepted proposals pending canonical distillation?
open proposals I can meaningfully review?
unconsumed notes I can deepen/connect?
meaningful artifacts needing review?
new observation worth depositing?
```

If the answer remains no, go idle.

---

## Provenance and audit

Every `bb` state transition appends an event to:

```text
.blackboard/events.jsonl
```

Use Git identities distinct per agent where possible.

Commit subjects should include the relevant stable task/sub-task ID:

```text
T003-SUB002: implement auth middleware
```

Use:

```bash
bb history T003
bb history P0017
bb contributions hermes-01
```

to reconstruct who contributed what.

Contribution includes more than commits:

- notes;
- reports;
- proposals;
- reviews;
- challenges;
- hard objections;
- blocker resolution;
- verification;
- implementation.

Preserve provenance chains such as:

```text
N0048 → REPORT → P0017 → T008 → commit abc123
```

This enables later analysis of genuine cross-agent information handoffs.

---

## Anti-chat rule

Do not use the Blackboard as a group chat.

Prefer durable epistemic actions:

```text
NOTE
REPORT
PROPOSAL
REVIEW
CHALLENGE
```

Messages should deposit useful information that any agent can consume, not require a specific recipient to be online.

---

## Anti-transcript rule

Canonical PRD/task files contain distilled current truth, not deliberation transcripts.

Bad:

```text
Prime wanted PostgreSQL, Hermes wanted SQLite, OpenClaw agreed with Hermes...
```

Good:

```text
Database: SQLite for the MVP.
Rationale: single-node deployment; distributed database semantics are not required.
```

Historical discussion remains in proposal artifacts and the audit trail.

---

## Mandatory re-observation rule

After any meaningful state-changing action — completing/releasing a task, creating/resolving a blocker, consuming/promoting a note, amending/withdrawing/superseding/consolidating/distilling a proposal — re-read the minimal Blackboard state once before idling.

The purpose is to close the information loop:

```text
contribution → changed shared state → other/new opportunities
```

Do not busy-loop indefinitely. Stop when no material contribution is available.

---

## `bb` is mechanism, not intelligence

Allowed responsibilities:

- stable ID allocation;
- short `flock` critical sections;
- claim/lease/heartbeat enforcement;
- ownership checks for task coordination commands;
- append-only event recording;
- proposal stance/objection bookkeeping;
- proposal revision/retirement/distillation bookkeeping;
- formal consensus-threshold validation;
- deterministic `NEW_TASK` materialization;
- status/history/search display.

Forbidden responsibilities:

- choosing the best agent;
- deciding which architecture is semantically best;
- ranking proposals by quality;
- inventing tasks without agent consensus;
- automatically overriding hard objections;
- planning the project on behalf of the agents.

Policy lives in agents using this skill. Mechanism lives in `bb`.
