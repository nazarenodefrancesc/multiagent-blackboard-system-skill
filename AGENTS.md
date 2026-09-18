# Agent bootstrap

This repository implements and dogfoods the Blackboard Collaboration workflow.

When using the skill in a project:

1. Read `SKILL.md`.
2. Read the project's `PRD.md`.
3. Inspect `git status --short`.
4. Set a stable identity, for example `export BB_AGENT=hermes-01`.
5. Run `bb status` before choosing work.
6. If `bb status` shows an accepted proposal with pending canonical distillation that you can safely apply, close that information loop before unrelated new work.
7. Respect task claims: a live claim owns both `prd/Txxx.md` and `progress/PROGRESS-Txxx.md` canonically.
8. Use notes/reports/proposals for contributions to work owned by another agent.
9. Treat amendments as new proposal revisions: old reviewer stances no longer count.
10. Stage only your own files in a shared working tree; never assume unrelated dirty files are yours.
11. Re-read the Blackboard after meaningful state changes before idling.

`bb` is mechanism only. Do not treat it as a planner, judge, or manager agent.
