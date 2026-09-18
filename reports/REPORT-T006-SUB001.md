# REPORT-T006-SUB001 — Adversarial second-pass findings

## Related specification

- [T006](../prd/T006.md)
- Sub-task: T006-SUB001

## Purpose

Review v0.1.0 specifically for defects that could produce misleading behavior during Pilot 0 even though the existing happy-path tests pass.

## Findings

### F1 — Proposal amendments inherit stale reviewer stances — FIX NOW

`amend_proposal()` appended new content but left existing SUPPORT/NEUTRAL/CHALLENGE stances intact. A proposal could therefore become materially different after review and still remain formally ready without fresh review.

Required correction: proposal revisions must invalidate reviewer stances for the previous revision. Unresolved hard objections remain blocking until explicitly resolved.

### F2 — `NEW_TASK` textual amendments do not update structured materialization data — FIX NOW

The accepted task is rendered from `task_spec`, while generic amendment text only changes the report. A material amendment to title/objective/priority/dependencies/acceptance/verification could therefore be accepted but materialize the old task definition.

Required correction: add an explicit structured `amend-task` operation; document that material `NEW_TASK` changes use it.

### F3 — No explicit way to retire an open proposal — FIX NOW

The specification discusses rejected/scarted ideas, but v0.1.0 had no withdrawal/supersession lifecycle. Stale proposals could remain OPEN indefinitely and pollute the idle/review loop.

Required correction: author withdrawal plus mechanical supersession by an already accepted alternative.

### F4 — Accepted non-`NEW_TASK` proposal has no closed distillation loop — FIX NOW

Consolidation emitted `CANONICAL_DISTILLATION_REQUIRED` but provided no state/command to prove the accepted decision was actually distilled into canonical memory. This can leave accepted requirements discoverable only in reports.

Required correction: track `distillation_status=PENDING` and provide `bb distill Pxxxx --into <canonical-ref>` to close the loop with audit provenance.

### F5 — Skill command syntax and parser disagree on `--agent` placement — FIX NOW

The skill shows `bb claim T003 --agent hermes`, while argparse accepted only `bb --agent hermes claim T003`.

Required correction: accept `--agent` both before and after subcommands and regression-test the literal skill syntax.

### F6 — Human-readable note/proposal Markdown retains stale frontmatter status — FIX NOW

Machine JSON changed to CONSUMED/ACCEPTED while the Markdown frontmatter remained OPEN. Agents reading the artifact rather than JSON could infer stale state.

Required correction: synchronize the `status` frontmatter on state transitions.

### F7 — Completion event labels current repository HEAD as `commit` — FIX NOW

Concurrent work means HEAD may belong to another agent. Recording it as `commit` on the completing agent's event can falsely imply authorship.

Required correction: record `head_at_completion` as an observation, not an attributed commit.

### F8 — Validation/check coverage is too narrow — FIX NOW

Direct core calls could materialize invalid priority/dependency identifiers, and consistency checks did not validate live claim/task status or proposal report existence.

Required correction: strengthen deterministic validation without adding semantic judgment.

### F9 — Source-file collision protection absent — PILOT OBSERVE

Known limitation. Adding source leases/worktrees now would materially change the experiment. Keep as pilot target.

### F10 — Semantic duplicate-proposal detection absent — PILOT OBSERVE

Known limitation. The skill already tells agents to inspect overlap; keep the first pilot capable of revealing whether a semantic mechanism is actually needed.

### F11 — Persistent ID counter can lag manually added canonical IDs — FIX NOW

Dogfooding T006 exposed that `.blackboard/counters.json` can become stale when a project owner adds a task directly to canonical PRD state. A later `NEW_TASK` consolidation could then attempt to reuse an existing ID and fail.

Required correction: ID allocation takes the maximum of the persisted counter and IDs inferred from canonical/artifact state before allocating the next value; `bb check` also reports lagging counters.

### F12 — Revised NEW_TASK title can break proposal provenance link — FIX NOW

After adding structured task revisions, changing the proposed task title changed the slug used when rendering the new task's source-proposal link, but the original proposal report filename is intentionally stable. The resulting `prd/Txxx.md` link could point to a non-existent report.

Required correction: materialization links directly to the proposal state's stable `report_path`, never to a re-derived filename.

### F13 — Available-task ordering ignored active-work precedence — FIX NOW

The original Scalable Ralph routing contract prefers eligible `IN_PROGRESS` macro-tasks before starting new `PLANNED` work. v0.1.0 sorted available tasks only by priority and ID, so a higher-priority planned task could be presented before an orphaned active task after lease expiry.

Required correction: route eligible `IN_PROGRESS` tasks first, then priority and stable ID; only then route `PLANNED` work.

## Decision

Implement F1–F8 and F11–F13 before Pilot 0. Leave F9–F10 unchanged and observable.

## Remaining issues

- Source code still shares one working tree.
- No watcher automatically wakes idle agents.
- Fixed consensus threshold remains deliberate for Pilot 0.
