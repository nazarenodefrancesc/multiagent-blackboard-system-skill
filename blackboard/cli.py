from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    BBError,
    actor,
    append_event,
    available_tasks,
    claim_task,
    complete_claim,
    discover_root,
    ensure_layout,
    ensure_task_index_markers,
    heartbeat_claim,
    list_claims,
    parse_task_index,
    progress_status,
    release_claim,
    create_note,
    reply_note,
    consume_note,
    list_notes,
    search_notes,
    create_proposal,
    list_proposals,
    get_proposal,
    set_stance,
    object_proposal,
    resolve_objection,
    amend_proposal,
    amend_task_proposal,
    withdraw_proposal,
    supersede_proposal,
    consensus_state,
    consolidate_proposal,
    distill_proposal,
    history_for_ref,
    contributions_for_agent,
    check_consistency,
)


def _print_json(payload) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root or ".").resolve()
    prd = root / "PRD.md"
    if not prd.exists():
        prd.write_text(
            "# Project PRD\n\n## Project description\n\n"
            + (args.brief or "Add project brief here.")
            + "\n",
            encoding="utf-8",
        )
    ensure_layout(root)
    ensure_task_index_markers(root)
    append_event(root, "BLACKBOARD_INIT", actor(args.agent, required=False), project_root=str(root))
    print(f"Initialized Blackboard at {root}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = discover_root()
    tasks = parse_task_index(root)
    open_proposals = list_proposals(root, status="OPEN")
    accepted_proposals = list_proposals(root, status="ACCEPTED")
    payload = {
        "root": str(root),
        "tasks": [
            {
                **task,
                "progress_status": progress_status(root, task["id"]) if (root / "progress" / f"PROGRESS-{task['id']}.md").exists() else None,
            }
            for task in tasks.values()
        ],
        "claims": list_claims(root),
        "available": [task["id"] for task in available_tasks(root)],
        "open_notes": list_notes(root, unconsumed_only=True),
        "open_proposals": open_proposals,
        "pending_distillations": [
            proposal
            for proposal in accepted_proposals
            if proposal.get("distillation_status") == "PENDING"
        ],
    }
    if args.json:
        _print_json(payload)
        return 0
    print(f"Blackboard: {root}")
    print("Tasks:")
    for task in payload["tasks"]:
        claim = next((c for c in payload["claims"] if c["task"] == task["id"]), None)
        owner = f" claimed={claim['agent']}" if claim else ""
        print(f"  {task['id']} {task['status']:<11} {task['priority']} {task['title']}{owner}")
    print("Available:", ", ".join(payload["available"]) or "—")
    print(f"Open proposals: {len(payload['open_proposals'])}")
    print(f"Pending canonical distillations: {len(payload['pending_distillations'])}")
    print(f"Unconsumed notes: {len(payload['open_notes'])}")
    return 0


def cmd_available(args: argparse.Namespace) -> int:
    root = discover_root()
    tasks = available_tasks(root)
    if args.json:
        _print_json(tasks)
    else:
        for task in tasks:
            deps = ",".join(task["dependencies"]) or "—"
            print(f"{task['id']}\t{task['priority']}\tdeps={deps}\t{task['title']}")
    return 0


def cmd_claims(args: argparse.Namespace) -> int:
    root = discover_root()
    claims = list_claims(root, include_expired=args.all)
    if args.json:
        _print_json(claims)
    else:
        for claim in claims:
            suffix = " EXPIRED" if claim.get("expired") else ""
            print(f"{claim['task']}\t{claim['agent']}\tuntil={claim['expires_at']}{suffix}")
    return 0


def cmd_claim(args: argparse.Namespace) -> int:
    root = discover_root()
    payload = claim_task(root, args.task, actor(args.agent), args.lease)
    _print_json(payload) if args.json else print(f"Claimed {args.task} as {payload['agent']} until {payload['expires_at']}")
    return 0


def cmd_heartbeat(args: argparse.Namespace) -> int:
    root = discover_root()
    payload = heartbeat_claim(root, args.task, actor(args.agent), args.lease)
    print(f"Extended {args.task} until {payload['expires_at']}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    root = discover_root()
    release_claim(root, args.task, actor(args.agent), args.reason)
    print(f"Released {args.task}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    root = discover_root()
    complete_claim(root, args.task, actor(args.agent))
    print(f"Completed coordination lifecycle for {args.task}")
    return 0



def cmd_note(args: argparse.Namespace) -> int:
    root = discover_root()
    state = create_note(root, actor(args.agent), args.text, note_type=args.type, task=args.task)
    print(f"Created {state['id']}")
    return 0


def cmd_reply(args: argparse.Namespace) -> int:
    root = discover_root()
    reply_note(root, args.note, actor(args.agent), args.text)
    print(f"Replied to {args.note}")
    return 0


def cmd_notes(args: argparse.Namespace) -> int:
    root = discover_root()
    notes = list_notes(root, unconsumed_only=args.unconsumed, task=args.task)
    if args.json:
        _print_json(notes)
    else:
        for note in notes:
            print(f"{note['id']}\t{note['status']}\t{note['type']}\ttask={note.get('task') or '—'}\tauthor={note['author']}")
    return 0


def cmd_consume(args: argparse.Namespace) -> int:
    root = discover_root()
    state = consume_note(root, args.note, actor(args.agent), args.by)
    print(f"Consumed {args.note} by {state['consumed_by']}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    root = discover_root()
    results = search_notes(root, args.query)
    if args.json:
        _print_json(results)
    else:
        for item in results:
            print(f"{item['id']}\t{item['status']}\t{item['path']}")
    return 0


def _read_body(args: argparse.Namespace) -> str:
    if getattr(args, 'body_file', None):
        return Path(args.body_file).read_text(encoding='utf-8')
    return getattr(args, 'body', None) or getattr(args, 'objective', '')


def cmd_propose(args: argparse.Namespace) -> int:
    root = discover_root()
    body = _read_body(args)
    state = create_proposal(
        root,
        actor(args.agent),
        args.title,
        body,
        kind=args.kind,
        task=args.task,
        source_note=args.from_note,
    )
    print(f"Created {state['id']} -> {state['report_path']}")
    return 0


def cmd_propose_task(args: argparse.Namespace) -> int:
    root = discover_root()
    task_spec = {
        'title': args.title,
        'objective': args.objective,
        'priority': args.priority,
        'dependencies': args.depends or [],
        'acceptance': args.acceptance or [],
        'verification': args.verification or [],
    }
    body = (
        f"Create a new canonical macro-task.\n\n"
        f"Objective: {args.objective}\n\n"
        f"Priority: {args.priority}\n\n"
        f"Dependencies: {', '.join(args.depends or []) or '—'}"
    )
    state = create_proposal(
        root,
        actor(args.agent),
        args.title,
        body,
        kind='NEW_TASK',
        source_note=args.from_note,
        task_spec=task_spec,
    )
    print(f"Created {state['id']} NEW_TASK -> {state['report_path']}")
    return 0


def cmd_proposals(args: argparse.Namespace) -> int:
    root = discover_root()
    proposals = list_proposals(root, status=args.status)
    if args.json:
        _print_json(proposals)
    else:
        for state in proposals:
            c = consensus_state(state)
            print(f"{state['id']}\t{state['status']}\t{state['kind']}\tready={str(c['ready']).lower()}\t{state['title']}")
    return 0


def cmd_proposal_show(args: argparse.Namespace) -> int:
    root = discover_root()
    state = get_proposal(root, args.proposal)
    payload = dict(state)
    payload['consensus'] = consensus_state(state)
    _print_json(payload)
    return 0


def _stance(args: argparse.Namespace, stance: str) -> int:
    root = discover_root()
    state = set_stance(root, args.proposal, actor(args.agent), stance, args.comment)
    c = consensus_state(state)
    print(f"{stance} recorded for {args.proposal}; ready={str(c['ready']).lower()}")
    return 0


def cmd_support(args: argparse.Namespace) -> int:
    return _stance(args, 'SUPPORT')


def cmd_neutral(args: argparse.Namespace) -> int:
    return _stance(args, 'NEUTRAL')


def cmd_challenge(args: argparse.Namespace) -> int:
    return _stance(args, 'CHALLENGE')


def cmd_object(args: argparse.Namespace) -> int:
    root = discover_root()
    state, oid = object_proposal(root, args.proposal, actor(args.agent), args.reason)
    print(f"Created hard objection {oid} on {args.proposal}; ready={str(consensus_state(state)['ready']).lower()}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    root = discover_root()
    state = resolve_objection(root, args.objection, actor(args.agent), args.comment)
    print(f"Resolved {args.objection}; {state['id']} ready={str(consensus_state(state)['ready']).lower()}")
    return 0


def cmd_amend(args: argparse.Namespace) -> int:
    root = discover_root()
    amend_proposal(root, args.proposal, actor(args.agent), args.text)
    print(f"Amended {args.proposal}")
    return 0


def cmd_amend_task(args: argparse.Namespace) -> int:
    root = discover_root()
    dependencies = [] if args.clear_depends else args.depends
    state = amend_task_proposal(
        root,
        args.proposal,
        actor(args.agent),
        title=args.title,
        objective=args.objective,
        priority=args.priority,
        dependencies=dependencies,
        acceptance=args.acceptance,
        verification=args.verification,
        comment=args.comment,
    )
    print(f"Revised {args.proposal} to revision {state['revision']}; fresh review required")
    return 0


def cmd_withdraw(args: argparse.Namespace) -> int:
    root = discover_root()
    withdraw_proposal(root, args.proposal, actor(args.agent), args.reason)
    print(f"Withdrew {args.proposal}")
    return 0


def cmd_supersede(args: argparse.Namespace) -> int:
    root = discover_root()
    supersede_proposal(root, args.proposal, args.by, actor(args.agent), args.reason)
    print(f"Superseded {args.proposal} by {args.by}")
    return 0


def cmd_consolidate(args: argparse.Namespace) -> int:
    root = discover_root()
    state = consolidate_proposal(root, args.proposal, actor(args.agent))
    suffix = f" -> {state['materialized_task']}" if state.get('materialized_task') else ""
    print(f"Consolidated {args.proposal}{suffix}")
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    root = discover_root()
    state = distill_proposal(root, args.proposal, actor(args.agent), args.into, args.note)
    print(f"Distilled {args.proposal} into {', '.join(state['distilled_into'])}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    root = discover_root()
    events = history_for_ref(root, args.ref)
    if args.json:
        _print_json(events)
    else:
        for event in events:
            agent_name = event.get('agent', 'system')
            detail = {k: v for k, v in event.items() if k not in {'ts', 'agent', 'event'}}
            print(f"{event['ts']}\t{agent_name}\t{event['event']}\t{json.dumps(detail, sort_keys=True)}")
    return 0


def cmd_contributions(args: argparse.Namespace) -> int:
    root = discover_root()
    events = contributions_for_agent(root, args.agent_name)
    if args.json:
        _print_json(events)
    else:
        for event in events:
            detail = {k: v for k, v in event.items() if k not in {'ts', 'agent', 'event'}}
            print(f"{event['ts']}\t{event['event']}\t{json.dumps(detail, sort_keys=True)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = discover_root()
    issues = check_consistency(root)
    if args.json:
        _print_json({'ok': not issues, 'issues': issues})
    elif issues:
        print('Blackboard consistency: FAIL')
        for issue in issues:
            print(f"  - {issue}")
    else:
        print('Blackboard consistency: PASS')
    return 1 if issues else 0


def cmd_event(args: argparse.Namespace) -> int:
    root = discover_root()
    fields = {}
    if args.ref:
        fields['ref'] = args.ref
    if args.task:
        fields['task'] = args.task
    if args.message:
        fields['message'] = args.message
    event = append_event(root, args.type.upper(), actor(args.agent), **fields)
    _print_json(event) if args.json else print(f"Recorded {event['event']}")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bb", description="Controller-free Blackboard coordination CLI")
    parser.add_argument("--agent", help="Agent identity; defaults to BB_AGENT or git user.name")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Initialize Blackboard metadata/layout")
    p.add_argument("--root")
    p.add_argument("--brief")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="Show task/claim routing state")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("available", help="Show currently claimable tasks")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_available)

    p = sub.add_parser("claims", help="Show task claims")
    p.add_argument("--all", action="store_true", help="Include expired claims")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_claims)

    p = sub.add_parser("claim", help="Claim exclusive canonical ownership of a task")
    p.add_argument("task")
    p.add_argument("--lease", type=int, default=30, help="Lease duration in minutes")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("heartbeat", help="Extend a live task claim")
    p.add_argument("task")
    p.add_argument("--lease", type=int, default=30)
    p.set_defaults(func=cmd_heartbeat)

    p = sub.add_parser("release", help="Release a task claim")
    p.add_argument("task")
    p.add_argument("--reason")
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("complete", help="Release a task after canonical state is already COMPLETE")
    p.add_argument("task")
    p.set_defaults(func=cmd_complete)


    p = sub.add_parser("note", help="Deposit an unstructured shared note")
    p.add_argument("text")
    p.add_argument("--type", default="observation")
    p.add_argument("--task")
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("reply", help="Add evidence/interpretation to a note")
    p.add_argument("note")
    p.add_argument("text")
    p.set_defaults(func=cmd_reply)

    p = sub.add_parser("notes", help="List shared notes")
    p.add_argument("--unconsumed", action="store_true")
    p.add_argument("--task")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_notes)

    p = sub.add_parser("consume", help="Mark a note incorporated by another artifact/state")
    p.add_argument("note")
    p.add_argument("--by", required=True)
    p.set_defaults(func=cmd_consume)

    p = sub.add_parser("search", help="Search note contents")
    p.add_argument("query")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("propose", help="Create a canonical-change proposal")
    p.add_argument("--title", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--kind", default="OTHER")
    p.add_argument("--task")
    p.add_argument("--from-note")
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("propose-task", help="Propose a new canonical macro-task")
    p.add_argument("--title", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--priority", choices=["P0", "P1", "P2", "P3"], default="P2")
    p.add_argument("--depends", action="append")
    p.add_argument("--acceptance", action="append", required=True)
    p.add_argument("--verification", action="append", required=True)
    p.add_argument("--from-note")
    p.set_defaults(func=cmd_propose_task)

    p = sub.add_parser("proposals", help="List proposals")
    p.add_argument("--status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_proposals)

    p = sub.add_parser("proposal", help="Show proposal state and consensus")
    p.add_argument("proposal")
    p.set_defaults(func=cmd_proposal_show)

    for name, func, help_text in [
        ("support", cmd_support, "Support an open proposal"),
        ("neutral", cmd_neutral, "Record a neutral review"),
        ("challenge", cmd_challenge, "Challenge an open proposal without blocking it"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("proposal")
        p.add_argument("comment", nargs="?")
        p.set_defaults(func=func)

    p = sub.add_parser("object", help="Create a blocking hard objection")
    p.add_argument("proposal")
    p.add_argument("reason")
    p.set_defaults(func=cmd_object)

    p = sub.add_parser("resolve", help="Resolve your own hard objection")
    p.add_argument("objection")
    p.add_argument("comment", nargs="?")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("amend", help="Append an amendment to an open proposal")
    p.add_argument("proposal")
    p.add_argument("text")
    p.set_defaults(func=cmd_amend)

    p = sub.add_parser("amend-task", help="Apply a structured revision to a NEW_TASK proposal")
    p.add_argument("proposal")
    p.add_argument("--title")
    p.add_argument("--objective")
    p.add_argument("--priority", choices=["P0", "P1", "P2", "P3"])
    dep_group = p.add_mutually_exclusive_group()
    dep_group.add_argument("--depends", action="append")
    dep_group.add_argument("--clear-depends", action="store_true")
    p.add_argument("--acceptance", action="append")
    p.add_argument("--verification", action="append")
    p.add_argument("--comment")
    p.set_defaults(func=cmd_amend_task)

    p = sub.add_parser("withdraw", help="Withdraw your own open proposal")
    p.add_argument("proposal")
    p.add_argument("--reason")
    p.set_defaults(func=cmd_withdraw)

    p = sub.add_parser("supersede", help="Close an open proposal as superseded by an accepted alternative")
    p.add_argument("proposal")
    p.add_argument("--by", required=True, help="Accepted proposal that supersedes this one")
    p.add_argument("--reason")
    p.set_defaults(func=cmd_supersede)


    p = sub.add_parser("consolidate", help="Mechanically consolidate a formally ready proposal")
    p.add_argument("proposal")
    p.set_defaults(func=cmd_consolidate)

    p = sub.add_parser("distill", help="Record accepted proposal content as distilled into canonical memory")
    p.add_argument("proposal")
    p.add_argument("--into", action="append", required=True, help="PRD.md or prd/Txxx.md; repeatable")
    p.add_argument("--note")
    p.set_defaults(func=cmd_distill)

    p = sub.add_parser("history", help="Show audit events related to a stable reference")
    p.add_argument("ref")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("contributions", help="Show all audit events attributed to an agent")
    p.add_argument("agent_name")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_contributions)

    p = sub.add_parser("check", help="Check canonical Blackboard consistency")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("event", help="Append a generic attributable audit event")
    p.add_argument("type")
    p.add_argument("--ref")
    p.add_argument("--task")
    p.add_argument("--message")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_event)

    # Support identity both before and after a subcommand. The suppressed local
    # default preserves a root-level value when the subcommand form is absent.
    for command_parser in sub.choices.values():
        command_parser.add_argument(
            "--agent",
            default=argparse.SUPPRESS,
            help="Agent identity; may be supplied before or after the subcommand",
        )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BBError as exc:
        print(f"bb: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
