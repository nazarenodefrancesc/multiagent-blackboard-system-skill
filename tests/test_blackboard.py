from __future__ import annotations

import datetime as dt
import json
import multiprocessing as mp
import tempfile
import unittest
from pathlib import Path

from blackboard.core import (
    BBError,
    amend_proposal,
    amend_task_proposal,
    available_tasks,
    check_consistency,
    claim_path,
    claim_task,
    complete_claim,
    consensus_state,
    consolidate_proposal,
    consume_note,
    contributions_for_agent,
    create_note,
    create_proposal,
    distill_proposal,
    ensure_layout,
    get_note,
    get_proposal,
    heartbeat_claim,
    history_for_ref,
    list_notes,
    object_proposal,
    parse_task_index,
    progress_status,
    release_claim,
    reply_note,
    resolve_objection,
    search_notes,
    set_stance,
    supersede_proposal,
    withdraw_proposal,
)
from blackboard.cli import build_parser


def _write_fixture(root: Path) -> None:
    (root / "prd").mkdir(parents=True)
    (root / "progress").mkdir()
    (root / "reports").mkdir()
    prd_text = (
        "# Fixture\n\n## Macro-task index\n\n"
        "<!-- BB:TASK_INDEX:START -->\n"
        "| ID | Macro-task | Status | Priority | Dependencies | Specification | Progress |\n"
        "|---|---|---|---|---|---|---|\n"
        "| T001 | First | PLANNED | P0 | — | [T001](prd/T001.md) | [PROGRESS-T001](progress/PROGRESS-T001.md) |\n"
        "| T002 | Second | PLANNED | P1 | T001 | [T002](prd/T002.md) | [PROGRESS-T002](progress/PROGRESS-T002.md) |\n"
        "<!-- BB:TASK_INDEX:END -->\n"
    )
    (root / "PRD.md").write_text(prd_text, encoding="utf-8")
    for task_id, title in [("T001", "First"), ("T002", "Second")]:
        (root / "prd" / f"{task_id}.md").write_text(
            f"# {task_id} — {title}\n\n## Objective\n\nFixture.\n", encoding="utf-8"
        )
        (root / "progress" / f"PROGRESS-{task_id}.md").write_text(
            f"# PROGRESS-{task_id}\n\n## Current state\n\n- Status: PLANNED\n- Active sub-task: —\n",
            encoding="utf-8",
        )
    ensure_layout(root)


def _set_status(root: Path, task_id: str, status: str) -> None:
    prd = root / "PRD.md"
    text = prd.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.startswith(f"| {task_id} |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            cells[2] = status
            line = "| " + " | ".join(cells) + " |"
        lines.append(line)
    prd.write_text("\n".join(lines) + "\n", encoding="utf-8")
    progress = root / "progress" / f"PROGRESS-{task_id}.md"
    ptext = progress.read_text(encoding="utf-8")
    ptext = ptext.replace("- Status: PLANNED", f"- Status: {status}")
    ptext = ptext.replace("- Status: IN_PROGRESS", f"- Status: {status}")
    progress.write_text(ptext, encoding="utf-8")


def _claim_worker(root_str: str, agent: str, queue: mp.Queue) -> None:
    try:
        claim_task(Path(root_str), "T001", agent, 30)
        queue.put((agent, True))
    except BBError:
        queue.put((agent, False))


class BlackboardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write_fixture(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_available_respects_dependencies(self) -> None:
        self.assertEqual([t["id"] for t in available_tasks(self.root)], ["T001"])
        _set_status(self.root, "T001", "COMPLETE")
        self.assertEqual([t["id"] for t in available_tasks(self.root)], ["T002"])

    def test_available_prefers_in_progress_before_planned(self) -> None:
        prd = self.root / "PRD.md"
        text = prd.read_text(encoding="utf-8")
        text = text.replace(
            "| T001 | First | PLANNED | P0 | — |",
            "| T001 | First | IN_PROGRESS | P1 | — |",
        )
        text = text.replace(
            "| T002 | Second | PLANNED | P1 | T001 |",
            "| T002 | Second | PLANNED | P0 | — |",
        )
        prd.write_text(text, encoding="utf-8")
        progress = self.root / "progress" / "PROGRESS-T001.md"
        progress.write_text(
            progress.read_text(encoding="utf-8").replace("- Status: PLANNED", "- Status: IN_PROGRESS"),
            encoding="utf-8",
        )
        self.assertEqual([t["id"] for t in available_tasks(self.root)], ["T001", "T002"])

    def test_claim_rejects_unsatisfied_dependencies(self) -> None:
        with self.assertRaises(BBError):
            claim_task(self.root, "T002", "agent-a", 30)
        _set_status(self.root, "T001", "COMPLETE")
        claim = claim_task(self.root, "T002", "agent-a", 30)
        self.assertEqual(claim["task"], "T002")

    def test_claim_exclusive_owner_heartbeat_release(self) -> None:
        claim = claim_task(self.root, "T001", "agent-a", 30)
        self.assertEqual(claim["agent"], "agent-a")
        with self.assertRaises(BBError):
            claim_task(self.root, "T001", "agent-b", 30)
        with self.assertRaises(BBError):
            heartbeat_claim(self.root, "T001", "agent-b", 30)
        heartbeat_claim(self.root, "T001", "agent-a", 45)
        with self.assertRaises(BBError):
            release_claim(self.root, "T001", "agent-b")
        release_claim(self.root, "T001", "agent-a")
        self.assertFalse(claim_path(self.root, "T001").exists())

    def test_expired_claim_can_be_taken_over(self) -> None:
        claim_task(self.root, "T001", "agent-a", 30)
        path = claim_path(self.root, "T001")
        claim = json.loads(path.read_text(encoding="utf-8"))
        claim["expires_at"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
        path.write_text(json.dumps(claim), encoding="utf-8")
        takeover = claim_task(self.root, "T001", "agent-b", 30)
        self.assertEqual(takeover["agent"], "agent-b")
        events = history_for_ref(self.root, "T001")
        self.assertIn("CLAIM_EXPIRED", [e["event"] for e in events])

    def test_concurrent_claim_has_single_winner(self) -> None:
        queue: mp.Queue = mp.Queue()
        a = mp.Process(target=_claim_worker, args=(str(self.root), "agent-a", queue))
        b = mp.Process(target=_claim_worker, args=(str(self.root), "agent-b", queue))
        a.start(); b.start(); a.join(10); b.join(10)
        self.assertFalse(a.is_alive())
        self.assertFalse(b.is_alive())
        results = [queue.get(timeout=2), queue.get(timeout=2)]
        self.assertEqual(sum(1 for _, ok in results if ok), 1)

    def test_complete_is_validator_not_decider(self) -> None:
        claim_task(self.root, "T001", "agent-a", 30)
        with self.assertRaises(BBError):
            complete_claim(self.root, "T001", "agent-a")
        _set_status(self.root, "T001", "COMPLETE")
        complete_claim(self.root, "T001", "agent-a")
        self.assertFalse(claim_path(self.root, "T001").exists())

    def test_note_reply_search_and_consumption(self) -> None:
        note = create_note(self.root, "agent-a", "Possible API rate limit", task="T001", note_type="warning")
        reply_note(self.root, note["id"], "agent-b", "Confirmed in provider docs")
        self.assertEqual(search_notes(self.root, "provider docs")[0]["id"], note["id"])
        consume_note(self.root, note["id"], "agent-b", "T001")
        loaded = get_note(self.root, note["id"])
        self.assertEqual(loaded["status"], "CONSUMED")
        self.assertEqual(list_notes(self.root, unconsumed_only=True), [])

    def test_note_promotion_consumes_note(self) -> None:
        note = create_note(self.root, "agent-a", "Migrations may be required")
        proposal = create_proposal(
            self.root,
            "agent-b",
            "Add migrations",
            "Create migration support.",
            kind="NEW_TASK",
            source_note=note["id"],
            task_spec={
                "title": "Add migrations",
                "objective": "Add migrations",
                "priority": "P1",
                "dependencies": [],
                "acceptance": ["Migration command works"],
                "verification": ["Run migration test"],
            },
        )
        self.assertEqual(get_note(self.root, note["id"])["consumed_by"], proposal["id"])
        note_md = (self.root / ".blackboard" / "notes" / f"{note['id']}.md").read_text(encoding="utf-8")
        self.assertIn("status: CONSUMED", note_md)

    def test_consensus_excludes_author_and_tracks_latest_stance(self) -> None:
        proposal = create_proposal(self.root, "author", "Choice", "Choose X")
        set_stance(self.root, proposal["id"], "author", "SUPPORT")
        set_stance(self.root, proposal["id"], "b", "SUPPORT")
        set_stance(self.root, proposal["id"], "c", "SUPPORT")
        self.assertFalse(consensus_state(get_proposal(self.root, proposal["id"]))["ready"])
        set_stance(self.root, proposal["id"], "d", "NEUTRAL")
        self.assertTrue(consensus_state(get_proposal(self.root, proposal["id"]))["ready"])
        set_stance(self.root, proposal["id"], "c", "CHALLENGE")
        state = consensus_state(get_proposal(self.root, proposal["id"]))
        self.assertEqual(state["supporters"], 1)
        self.assertFalse(state["ready"])

    def test_amendment_requires_fresh_review(self) -> None:
        proposal = create_proposal(self.root, "author", "Choice", "Choose X")
        set_stance(self.root, proposal["id"], "b", "SUPPORT")
        set_stance(self.root, proposal["id"], "c", "SUPPORT")
        set_stance(self.root, proposal["id"], "d", "NEUTRAL")
        self.assertTrue(consensus_state(get_proposal(self.root, proposal["id"]))["ready"])

        amend_proposal(self.root, proposal["id"], "author", "Use X only when condition Y holds")
        amended = get_proposal(self.root, proposal["id"])
        self.assertEqual(amended["revision"], 2)
        self.assertFalse(consensus_state(amended)["ready"])

        set_stance(self.root, proposal["id"], "b", "SUPPORT")
        set_stance(self.root, proposal["id"], "c", "SUPPORT")
        set_stance(self.root, proposal["id"], "d", "NEUTRAL")
        self.assertTrue(consensus_state(get_proposal(self.root, proposal["id"]))["ready"])

    def test_structured_task_revision_is_materialized(self) -> None:
        proposal = create_proposal(
            self.root,
            "author",
            "Initial migrations",
            "Add migrations.",
            kind="NEW_TASK",
            task_spec={
                "title": "Initial migrations",
                "objective": "Old objective",
                "priority": "P2",
                "dependencies": [],
                "acceptance": ["Old acceptance"],
                "verification": ["Old verification"],
            },
        )
        amend_task_proposal(
            self.root,
            proposal["id"],
            "author",
            title="Database migrations",
            objective="New objective",
            priority="P1",
            dependencies=["T001"],
            acceptance=["New acceptance"],
            verification=["New verification"],
        )
        for agent, stance in [("b", "SUPPORT"), ("c", "SUPPORT"), ("d", "NEUTRAL")]:
            set_stance(self.root, proposal["id"], agent, stance)
        accepted = consolidate_proposal(self.root, proposal["id"], "b")
        task_id = accepted["materialized_task"]
        spec = (self.root / "prd" / f"{task_id}.md").read_text(encoding="utf-8")
        self.assertIn("Database migrations", spec)
        self.assertIn("New objective", spec)
        self.assertIn("New acceptance", spec)
        self.assertIn(f"../{accepted['report_path']}", spec)
        self.assertTrue((self.root / accepted["report_path"]).exists())
        task = parse_task_index(self.root)[task_id]
        self.assertEqual(task["priority"], "P1")
        self.assertEqual(task["dependencies"], ["T001"])

    def test_withdraw_and_supersede_lifecycle(self) -> None:
        withdrawn = create_proposal(self.root, "author", "Old idea", "Try old idea")
        with self.assertRaises(BBError):
            withdraw_proposal(self.root, withdrawn["id"], "other")
        state = withdraw_proposal(self.root, withdrawn["id"], "author", "No longer useful")
        self.assertEqual(state["status"], "WITHDRAWN")

        old = create_proposal(self.root, "old-author", "Alternative A", "Use A")
        accepted = create_proposal(self.root, "new-author", "Alternative B", "Use B")
        for agent, stance in [("b", "SUPPORT"), ("c", "SUPPORT"), ("d", "NEUTRAL")]:
            set_stance(self.root, accepted["id"], agent, stance)
        consolidate_proposal(self.root, accepted["id"], "b")
        superseded = supersede_proposal(self.root, old["id"], accepted["id"], "b")
        self.assertEqual(superseded["status"], "SUPERSEDED")
        self.assertEqual(superseded["superseded_by"], accepted["id"])

    def test_non_task_proposal_requires_and_records_distillation(self) -> None:
        proposal = create_proposal(self.root, "author", "Global rule", "Document global rule")
        for agent, stance in [("b", "SUPPORT"), ("c", "SUPPORT"), ("d", "NEUTRAL")]:
            set_stance(self.root, proposal["id"], agent, stance)
        accepted = consolidate_proposal(self.root, proposal["id"], "b")
        self.assertEqual(accepted["distillation_status"], "PENDING")
        distilled = distill_proposal(self.root, proposal["id"], "b", ["PRD.md"], "Applied global rule")
        self.assertEqual(distilled["distillation_status"], "COMPLETE")
        self.assertEqual(distilled["distilled_into"], ["PRD.md"])
        self.assertIn("PROPOSAL_DISTILLED", [e["event"] for e in history_for_ref(self.root, proposal["id"])])

    def test_task_distillation_requires_live_claim(self) -> None:
        proposal = create_proposal(self.root, "author", "Task rule", "Change task rule", task="T001")
        for agent, stance in [("b", "SUPPORT"), ("c", "SUPPORT"), ("d", "NEUTRAL")]:
            set_stance(self.root, proposal["id"], agent, stance)
        consolidate_proposal(self.root, proposal["id"], "b")
        with self.assertRaises(BBError):
            distill_proposal(self.root, proposal["id"], "b", ["prd/T001.md"])
        claim_task(self.root, "T001", "b", 30)
        distilled = distill_proposal(self.root, proposal["id"], "b", ["prd/T001.md"])
        self.assertEqual(distilled["distillation_status"], "COMPLETE")

    def test_task_scoped_proposal_cannot_distill_into_other_task(self) -> None:
        proposal = create_proposal(self.root, "author", "Task rule", "Change task rule", task="T001")
        for agent, stance in [("b", "SUPPORT"), ("c", "SUPPORT"), ("d", "NEUTRAL")]:
            set_stance(self.root, proposal["id"], agent, stance)
        consolidate_proposal(self.root, proposal["id"], "b")
        with self.assertRaises(BBError):
            distill_proposal(self.root, proposal["id"], "b", ["prd/T002.md"])

    def test_hard_objection_blocks_until_author_resolves(self) -> None:
        proposal = create_proposal(self.root, "author", "Choice", "Choose X")
        set_stance(self.root, proposal["id"], "b", "SUPPORT")
        set_stance(self.root, proposal["id"], "c", "SUPPORT")
        set_stance(self.root, proposal["id"], "d", "NEUTRAL")
        _, oid = object_proposal(self.root, proposal["id"], "e", "Violates requirement R1")
        self.assertFalse(consensus_state(get_proposal(self.root, proposal["id"]))["ready"])
        with self.assertRaises(BBError):
            resolve_objection(self.root, oid, "b")
        resolve_objection(self.root, oid, "e", "R1 was updated; objection withdrawn")
        self.assertTrue(consensus_state(get_proposal(self.root, proposal["id"]))["ready"])

    def test_consolidation_requires_consensus(self) -> None:
        proposal = create_proposal(self.root, "author", "Choice", "Choose X")
        with self.assertRaises(BBError):
            consolidate_proposal(self.root, proposal["id"], "b")

    def test_new_task_materialization(self) -> None:
        proposal = create_proposal(
            self.root,
            "author",
            "Database migrations",
            "Add deterministic migrations.",
            kind="NEW_TASK",
            task_spec={
                "title": "Database migrations",
                "objective": "Add deterministic migrations.",
                "priority": "P1",
                "dependencies": ["T001"],
                "acceptance": ["Migration can be applied and rolled forward"],
                "verification": ["Run migration integration test"],
            },
        )
        set_stance(self.root, proposal["id"], "b", "SUPPORT")
        set_stance(self.root, proposal["id"], "c", "SUPPORT")
        set_stance(self.root, proposal["id"], "d", "NEUTRAL")
        accepted = consolidate_proposal(self.root, proposal["id"], "b")
        self.assertEqual(accepted["status"], "ACCEPTED")
        self.assertEqual(accepted["materialized_task"], "T003")
        tasks = parse_task_index(self.root)
        self.assertIn("T003", tasks)
        self.assertEqual(tasks["T003"]["dependencies"], ["T001"])
        self.assertEqual(progress_status(self.root, "T003"), "PLANNED")
        self.assertTrue((self.root / "prd" / "T003.md").exists())
        self.assertTrue((self.root / "progress" / "PROGRESS-T003.md").exists())
        self.assertIn("TASK_CREATED", [e["event"] for e in history_for_ref(self.root, "T003")])
        report = (self.root / accepted["report_path"]).read_text(encoding="utf-8")
        self.assertIn("status: ACCEPTED", report)

    def test_id_allocation_self_heals_stale_counter(self) -> None:
        counters_path = self.root / ".blackboard" / "counters.json"
        counters = json.loads(counters_path.read_text(encoding="utf-8"))
        counters["task"] = 0
        counters_path.write_text(json.dumps(counters), encoding="utf-8")

        proposal = create_proposal(
            self.root,
            "author",
            "Third task",
            "Create a third task.",
            kind="NEW_TASK",
            task_spec={
                "title": "Third task",
                "objective": "Create third task",
                "priority": "P2",
                "dependencies": [],
                "acceptance": ["Task exists"],
                "verification": ["Inspect task"],
            },
        )
        for agent, stance in [("b", "SUPPORT"), ("c", "SUPPORT"), ("d", "NEUTRAL")]:
            set_stance(self.root, proposal["id"], agent, stance)
        accepted = consolidate_proposal(self.root, proposal["id"], "b")
        self.assertEqual(accepted["materialized_task"], "T003")

    def test_agent_option_works_before_and_after_subcommand(self) -> None:
        parser = build_parser()
        before = parser.parse_args(["--agent", "agent-a", "status"])
        after = parser.parse_args(["status", "--agent", "agent-b"])
        self.assertEqual(before.agent, "agent-a")
        self.assertEqual(after.agent, "agent-b")

    def test_contributions_and_consistency(self) -> None:
        create_note(self.root, "agent-a", "Observation")
        events = contributions_for_agent(self.root, "agent-a")
        self.assertEqual(events[-1]["event"], "NOTE_CREATED")
        self.assertEqual(check_consistency(self.root), [])
        progress = self.root / "progress" / "PROGRESS-T001.md"
        progress.write_text(progress.read_text().replace("PLANNED", "BLOCKED"), encoding="utf-8")
        issues = check_consistency(self.root)
        self.assertTrue(any("root status PLANNED != progress status BLOCKED" in issue for issue in issues))

    def test_consistency_detects_human_machine_note_status_drift(self) -> None:
        note = create_note(self.root, "agent-a", "Observation")
        consume_note(self.root, note["id"], "agent-a", "T001")
        md_path = self.root / ".blackboard" / "notes" / f"{note['id']}.md"
        md_path.write_text(md_path.read_text(encoding="utf-8").replace("status: CONSUMED", "status: OPEN"), encoding="utf-8")
        issues = check_consistency(self.root)
        self.assertTrue(any(f"{note['id']}: Markdown status OPEN != state status CONSUMED" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
