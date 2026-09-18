from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator

TASK_ID_RE = re.compile(r"^T\d{3,}$")
NOTE_ID_RE = re.compile(r"^N\d{4,}$")
PROPOSAL_ID_RE = re.compile(r"^P\d{4,}$")
OBJECTION_ID_RE = re.compile(r"^O\d{4,}$")
PROGRESS_STATUS_RE = re.compile(r"^- Status:\s*([A-Z_]+)\s*$", re.MULTILINE)
TASK_INDEX_START = "<!-- BB:TASK_INDEX:START -->"
TASK_INDEX_END = "<!-- BB:TASK_INDEX:END -->"
VALID_STATUSES = {
    "PLANNED",
    "IN_PROGRESS",
    "BLOCKED",
    "IN_REVIEW",
    "COMPLETE",
    "DEFERRED",
    "CANCELLED",
}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_PROPOSAL_STATUSES = {"OPEN", "ACCEPTED", "WITHDRAWN", "SUPERSEDED"}


class BBError(RuntimeError):
    """Expected user-facing coordination error."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def discover_root(start: str | Path | None = None) -> Path:
    env_root = os.environ.get("BB_ROOT")
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if not (root / "PRD.md").exists():
            raise BBError(f"BB_ROOT does not contain PRD.md: {root}")
        return root

    current = Path(start or os.getcwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "PRD.md").exists():
            return candidate
    raise BBError("No Blackboard project found. Expected PRD.md in current directory or a parent.")


def bb_dir(root: Path) -> Path:
    return root / ".blackboard"


def ensure_layout(root: Path) -> None:
    base = bb_dir(root)
    for name in ("claims", "notes", "proposals", "agents"):
        (base / name).mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "prd").mkdir(parents=True, exist_ok=True)
    (root / "progress").mkdir(parents=True, exist_ok=True)
    events = base / "events.jsonl"
    events.touch(exist_ok=True)
    counters = base / "counters.json"
    if not counters.exists():
        initial = _infer_counters(root)
        atomic_write_json(counters, initial)


def _infer_counters(root: Path) -> dict[str, int]:
    def max_id(paths: list[Path], pattern: re.Pattern[str], prefix: str) -> int:
        best = 0
        for path in paths:
            stem = path.stem
            match = re.search(rf"{re.escape(prefix)}(\d+)", stem)
            if match:
                best = max(best, int(match.group(1)))
        return best

    task_max = max_id(list((root / "prd").glob("T*.md")), TASK_ID_RE, "T")
    prd_path = root / "PRD.md"
    if prd_path.exists():
        for match in re.finditer(r"\bT(\d{3,})\b", prd_path.read_text(encoding="utf-8")):
            task_max = max(task_max, int(match.group(1)))

    objection_max = 0
    proposals_dir = bb_dir(root) / "proposals"
    if proposals_dir.exists():
        for path in proposals_dir.glob("P*.json"):
            state = read_json(path, {}) or {}
            for objection_id in state.get("objections", {}):
                match = re.match(r"^O(\d+)$", str(objection_id))
                if match:
                    objection_max = max(objection_max, int(match.group(1)))

    return {
        "task": task_max,
        "note": max_id(list((bb_dir(root) / "notes").glob("N*.md")), NOTE_ID_RE, "N"),
        "proposal": max_id(list((bb_dir(root) / "proposals").glob("P*.json")), PROPOSAL_ID_RE, "P"),
        "objection": objection_max,
    }


@contextlib.contextmanager
def locked(root: Path) -> Iterator[None]:
    ensure_layout(root)
    lock_path = bb_dir(root) / "lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def update_frontmatter_field(path: Path, key: str, value: str) -> None:
    """Update a simple scalar in the first YAML-style Markdown frontmatter block."""
    if not path.exists():
        raise BBError(f"Missing Markdown artifact: {path}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise BBError(f"Missing frontmatter in {path}")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise BBError(f"Unterminated frontmatter in {path}") from exc
    prefix = f"{key}:"
    for i in range(1, end):
        if lines[i].startswith(prefix):
            lines[i] = f"{key}: {value}"
            break
    else:
        lines.insert(end, f"{key}: {value}")
    atomic_write_text(path, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))


def read_frontmatter_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def append_event_unlocked(root: Path, event: str, agent: str | None = None, **fields: Any) -> dict[str, Any]:
    ensure_layout(root)
    payload: dict[str, Any] = {"ts": iso_now(), "event": event}
    if agent:
        payload["agent"] = agent
    payload.update({k: v for k, v in fields.items() if v is not None})
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    with (bb_dir(root) / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return payload


def append_event(root: Path, event: str, agent: str | None = None, **fields: Any) -> dict[str, Any]:
    with locked(root):
        return append_event_unlocked(root, event, agent, **fields)


def read_events(root: Path) -> list[dict[str, Any]]:
    path = bb_dir(root) / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return events


def actor(explicit: str | None = None, *, required: bool = True) -> str | None:
    value = explicit or os.environ.get("BB_AGENT")
    if not value:
        try:
            proc = subprocess.run(
                ["git", "config", "user.name"],
                check=False,
                capture_output=True,
                text=True,
            )
            value = proc.stdout.strip() or None
        except OSError:
            value = None
    if required and not value:
        raise BBError("Agent identity required. Pass --agent or set BB_AGENT.")
    return value


def _allocate_id_unlocked(root: Path, kind: str, prefix: str, width: int) -> str:
    counters_path = bb_dir(root) / "counters.json"
    counters = read_json(counters_path, {}) or {}
    inferred = _infer_counters(root)
    current = max(int(counters.get(kind, 0)), int(inferred.get(kind, 0))) + 1
    counters[kind] = current
    atomic_write_json(counters_path, counters)
    return f"{prefix}{current:0{width}d}"


def allocate_id(root: Path, kind: str, prefix: str, width: int) -> str:
    with locked(root):
        return _allocate_id_unlocked(root, kind, prefix, width)


def parse_task_index(root: Path) -> dict[str, dict[str, Any]]:
    text = (root / "PRD.md").read_text(encoding="utf-8")
    if TASK_INDEX_START not in text or TASK_INDEX_END not in text:
        raise BBError("PRD.md is missing Blackboard task-index markers. Run `bb init` or add them explicitly.")
    block = text.split(TASK_INDEX_START, 1)[1].split(TASK_INDEX_END, 1)[0]
    tasks: dict[str, dict[str, Any]] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7 or not TASK_ID_RE.match(cells[0]):
            continue
        deps_raw = cells[4]
        deps = [] if deps_raw in {"", "—", "-"} else [d.strip() for d in deps_raw.split(",") if d.strip()]
        tasks[cells[0]] = {
            "id": cells[0],
            "title": cells[1],
            "status": cells[2],
            "priority": cells[3],
            "dependencies": deps,
            "spec_cell": cells[5],
            "progress_cell": cells[6],
        }
    return tasks


def task_exists(root: Path, task_id: str) -> bool:
    return task_id in parse_task_index(root) and (root / "prd" / f"{task_id}.md").exists()


def progress_status(root: Path, task_id: str) -> str:
    path = root / "progress" / f"PROGRESS-{task_id}.md"
    if not path.exists():
        raise BBError(f"Missing progress file: {path.relative_to(root)}")
    match = PROGRESS_STATUS_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise BBError(f"Could not parse status from {path.relative_to(root)}")
    return match.group(1)


def root_task_status(root: Path, task_id: str) -> str:
    tasks = parse_task_index(root)
    if task_id not in tasks:
        raise BBError(f"Unknown task: {task_id}")
    return str(tasks[task_id]["status"])


def claim_path(root: Path, task_id: str) -> Path:
    return bb_dir(root) / "claims" / f"{task_id}.json"


def _claim_is_expired(claim: dict[str, Any], now: dt.datetime | None = None) -> bool:
    now = now or utc_now()
    return parse_iso(claim["expires_at"]) <= now


def get_claim(root: Path, task_id: str, *, include_expired: bool = False) -> dict[str, Any] | None:
    claim = read_json(claim_path(root, task_id))
    if not claim:
        return None
    if not include_expired and _claim_is_expired(claim):
        return None
    return claim


def claim_task(root: Path, task_id: str, agent_name: str, lease_minutes: int = 30) -> dict[str, Any]:
    if lease_minutes <= 0:
        raise BBError("Lease must be greater than zero minutes.")
    with locked(root):
        tasks = parse_task_index(root)
        if task_id not in tasks:
            raise BBError(f"Unknown task: {task_id}")
        spec_path = root / "prd" / f"{task_id}.md"
        progress_path = root / "progress" / f"PROGRESS-{task_id}.md"
        if not spec_path.exists() or not progress_path.exists():
            raise BBError(f"Task {task_id} is missing its canonical specification or progress file.")
        prog_status = progress_status(root, task_id)
        if prog_status != tasks[task_id]["status"]:
            raise BBError(
                f"Task {task_id} has inconsistent canonical state: "
                f"root={tasks[task_id]['status']}, progress={prog_status}. Run `bb check`."
            )
        if tasks[task_id]["status"] in {"COMPLETE", "CANCELLED", "DEFERRED", "BLOCKED", "IN_REVIEW"}:
            raise BBError(f"Task {task_id} is {tasks[task_id]['status']} and is not claimable as implementation work.")
        incomplete_dependencies = [
            dep for dep in tasks[task_id].get("dependencies", [])
            if dep not in tasks or tasks[dep]["status"] != "COMPLETE"
        ]
        if incomplete_dependencies:
            raise BBError(
                f"Task {task_id} has unsatisfied dependencies: {', '.join(incomplete_dependencies)}."
            )
        existing = read_json(claim_path(root, task_id))
        if existing and not _claim_is_expired(existing):
            if existing.get("agent") == agent_name:
                raise BBError(f"{agent_name} already owns {task_id}; use heartbeat to extend the lease.")
            raise BBError(f"{task_id} is claimed by {existing.get('agent')} until {existing.get('expires_at')}.")
        if existing and _claim_is_expired(existing):
            append_event_unlocked(
                root,
                "CLAIM_EXPIRED",
                existing.get("agent"),
                task=task_id,
                expired_at=existing.get("expires_at"),
            )
        now = utc_now()
        payload = {
            "task": task_id,
            "agent": agent_name,
            "claimed_at": now.isoformat(timespec="seconds"),
            "heartbeat_at": now.isoformat(timespec="seconds"),
            "expires_at": (now + dt.timedelta(minutes=lease_minutes)).isoformat(timespec="seconds"),
        }
        atomic_write_json(claim_path(root, task_id), payload)
        append_event_unlocked(root, "CLAIM", agent_name, task=task_id, expires_at=payload["expires_at"])
        return payload


def heartbeat_claim(root: Path, task_id: str, agent_name: str, lease_minutes: int = 30) -> dict[str, Any]:
    if lease_minutes <= 0:
        raise BBError("Lease must be greater than zero minutes.")
    with locked(root):
        claim = read_json(claim_path(root, task_id))
        if not claim or _claim_is_expired(claim):
            raise BBError(f"No live claim exists for {task_id}.")
        if claim.get("agent") != agent_name:
            raise BBError(f"{task_id} is owned by {claim.get('agent')}, not {agent_name}.")
        now = utc_now()
        claim["heartbeat_at"] = now.isoformat(timespec="seconds")
        claim["expires_at"] = (now + dt.timedelta(minutes=lease_minutes)).isoformat(timespec="seconds")
        atomic_write_json(claim_path(root, task_id), claim)
        append_event_unlocked(root, "HEARTBEAT", agent_name, task=task_id, expires_at=claim["expires_at"])
        return claim


def release_claim(root: Path, task_id: str, agent_name: str, reason: str | None = None) -> None:
    with locked(root):
        path = claim_path(root, task_id)
        claim = read_json(path)
        if not claim:
            raise BBError(f"No claim exists for {task_id}.")
        if not _claim_is_expired(claim) and claim.get("agent") != agent_name:
            raise BBError(f"{task_id} is owned by {claim.get('agent')}, not {agent_name}.")
        path.unlink(missing_ok=True)
        append_event_unlocked(root, "RELEASE", agent_name, task=task_id, reason=reason)


def complete_claim(root: Path, task_id: str, agent_name: str) -> None:
    with locked(root):
        path = claim_path(root, task_id)
        claim = read_json(path)
        if not claim or _claim_is_expired(claim):
            raise BBError(f"No live claim exists for {task_id}.")
        if claim.get("agent") != agent_name:
            raise BBError(f"{task_id} is owned by {claim.get('agent')}, not {agent_name}.")
        root_status = root_task_status(root, task_id)
        prog_status = progress_status(root, task_id)
        if root_status != "COMPLETE" or prog_status != "COMPLETE":
            raise BBError(
                f"Cannot complete claim: canonical state is root={root_status}, progress={prog_status}. "
                "The owner must first verify work and update both canonical states to COMPLETE."
            )
        path.unlink(missing_ok=True)
        head = git_head(root)
        append_event_unlocked(root, "COMPLETE", agent_name, task=task_id, head_at_completion=head)


def list_claims(root: Path, *, include_expired: bool = False) -> list[dict[str, Any]]:
    ensure_layout(root)
    claims: list[dict[str, Any]] = []
    for path in sorted((bb_dir(root) / "claims").glob("T*.json")):
        claim = read_json(path)
        if not claim:
            continue
        expired = _claim_is_expired(claim)
        if expired and not include_expired:
            continue
        item = dict(claim)
        item["expired"] = expired
        claims.append(item)
    return claims


def available_tasks(root: Path) -> list[dict[str, Any]]:
    tasks = parse_task_index(root)
    complete = {tid for tid, task in tasks.items() if task["status"] == "COMPLETE"}
    available: list[dict[str, Any]] = []
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for task in tasks.values():
        if task["status"] not in {"PLANNED", "IN_PROGRESS"}:
            continue
        spec_path = root / "prd" / f"{task['id']}.md"
        progress_path = root / "progress" / f"PROGRESS-{task['id']}.md"
        if not spec_path.exists() or not progress_path.exists():
            continue
        try:
            if progress_status(root, task["id"]) != task["status"]:
                continue
        except BBError:
            continue
        if any(dep not in complete for dep in task["dependencies"]):
            continue
        if get_claim(root, task["id"]):
            continue
        available.append(task)
    status_rank = {"IN_PROGRESS": 0, "PLANNED": 1}
    return sorted(
        available,
        key=lambda t: (
            status_rank.get(t["status"], 99),
            priority_rank.get(t["priority"], 99),
            t["id"],
        ),
    )


def git_head(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    value = proc.stdout.strip()
    return value if proc.returncode == 0 and value else None


def ensure_task_index_markers(root: Path) -> None:
    path = root / "PRD.md"
    text = path.read_text(encoding="utf-8")
    if TASK_INDEX_START in text and TASK_INDEX_END in text:
        return
    addition = (
        "\n\n## Macro-task index\n\n"
        f"{TASK_INDEX_START}\n"
        "| ID | Macro-task | Status | Priority | Dependencies | Specification | Progress |\n"
        "|---|---|---|---|---|---|---|\n"
        f"{TASK_INDEX_END}\n"
    )
    atomic_write_text(path, text.rstrip() + addition)


def slugify(value: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (slug[:limit].rstrip("-") or "item")


def note_paths(root: Path, note_id: str) -> tuple[Path, Path]:
    base = bb_dir(root) / "notes"
    return base / f"{note_id}.md", base / f"{note_id}.json"


def create_note(
    root: Path,
    agent_name: str,
    text: str,
    *,
    note_type: str = "observation",
    task: str | None = None,
) -> dict[str, Any]:
    if not text.strip():
        raise BBError("Note text cannot be empty.")
    if task and task not in parse_task_index(root):
        raise BBError(f"Unknown task: {task}")
    with locked(root):
        note_id = _allocate_id_unlocked(root, "note", "N", 4)
        created = iso_now()
        md_path, state_path = note_paths(root, note_id)
        state = {
            "id": note_id,
            "author": agent_name,
            "created": created,
            "type": note_type,
            "task": task,
            "status": "OPEN",
            "consumed_by": None,
            "replies": [],
        }
        header = [
            "---",
            f"id: {note_id}",
            f"author: {agent_name}",
            f"created: {created}",
            f"type: {note_type}",
            f"task: {task or '—'}",
            "status: OPEN",
            "---",
            "",
            f"# {note_id} — {note_type}",
            "",
            text.strip(),
            "",
            "## Replies",
            "",
        ]
        atomic_write_text(md_path, "\n".join(header))
        atomic_write_json(state_path, state)
        append_event_unlocked(root, "NOTE_CREATED", agent_name, note=note_id, task=task, note_type=note_type)
        return state


def get_note(root: Path, note_id: str) -> dict[str, Any]:
    _, state_path = note_paths(root, note_id)
    state = read_json(state_path)
    if not state:
        raise BBError(f"Unknown note: {note_id}")
    return state


def reply_note(root: Path, note_id: str, agent_name: str, text: str) -> dict[str, Any]:
    if not text.strip():
        raise BBError("Reply text cannot be empty.")
    with locked(root):
        md_path, state_path = note_paths(root, note_id)
        state = read_json(state_path)
        if not state or not md_path.exists():
            raise BBError(f"Unknown note: {note_id}")
        reply = {"ts": iso_now(), "agent": agent_name, "text": text.strip()}
        state.setdefault("replies", []).append(reply)
        with md_path.open("a", encoding="utf-8") as handle:
            handle.write(f"### {reply['ts']} — {agent_name}\n\n{text.strip()}\n\n")
        atomic_write_json(state_path, state)
        append_event_unlocked(root, "NOTE_REPLY", agent_name, note=note_id, task=state.get("task"))
        return state


def consume_note(root: Path, note_id: str, agent_name: str, consumed_by: str) -> dict[str, Any]:
    if not consumed_by.strip():
        raise BBError("consumed_by cannot be empty.")
    with locked(root):
        md_path, state_path = note_paths(root, note_id)
        state = read_json(state_path)
        if not state or not md_path.exists():
            raise BBError(f"Unknown note: {note_id}")
        if state.get("status") == "CONSUMED":
            if state.get("consumed_by") == consumed_by:
                return state
            raise BBError(f"{note_id} is already consumed by {state.get('consumed_by')}.")
        state["status"] = "CONSUMED"
        state["consumed_by"] = consumed_by
        state["consumed_at"] = iso_now()
        state["consumed_by_agent"] = agent_name
        update_frontmatter_field(md_path, "status", "CONSUMED")
        with md_path.open("a", encoding="utf-8") as handle:
            handle.write(f"## Consumed\n\n- By: `{consumed_by}`\n- Agent: {agent_name}\n- At: {state['consumed_at']}\n")
        atomic_write_json(state_path, state)
        append_event_unlocked(
            root,
            "NOTE_CONSUMED",
            agent_name,
            note=note_id,
            task=state.get("task"),
            consumed_by=consumed_by,
        )
        return state


def list_notes(root: Path, *, unconsumed_only: bool = False, task: str | None = None) -> list[dict[str, Any]]:
    ensure_layout(root)
    notes: list[dict[str, Any]] = []
    for path in sorted((bb_dir(root) / "notes").glob("N*.json")):
        state = read_json(path)
        if not state:
            continue
        if unconsumed_only and state.get("status") != "OPEN":
            continue
        if task and state.get("task") != task:
            continue
        notes.append(state)
    return notes


def search_notes(root: Path, query: str) -> list[dict[str, Any]]:
    query_lower = query.lower()
    results: list[dict[str, Any]] = []
    for state in list_notes(root):
        md_path, _ = note_paths(root, state["id"])
        text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        if query_lower in text.lower():
            item = dict(state)
            item["path"] = str(md_path.relative_to(root))
            results.append(item)
    return results


def proposal_state_path(root: Path, proposal_id: str) -> Path:
    return bb_dir(root) / "proposals" / f"{proposal_id}.json"


def get_proposal(root: Path, proposal_id: str) -> dict[str, Any]:
    state = read_json(proposal_state_path(root, proposal_id))
    if not state:
        raise BBError(f"Unknown proposal: {proposal_id}")
    return state


def _validate_task_spec(spec: dict[str, Any]) -> None:
    required = ["title", "objective", "priority", "acceptance", "verification"]
    missing = [key for key in required if not spec.get(key)]
    if missing:
        raise BBError(f"NEW_TASK proposal missing task metadata: {', '.join(missing)}")
    if spec["priority"] not in VALID_PRIORITIES:
        raise BBError(f"Invalid task priority: {spec['priority']}")
    if "|" in str(spec["title"]):
        raise BBError("Task title cannot contain '|', because it would corrupt the Markdown task index.")
    dependencies = spec.get("dependencies") or []
    invalid = [dep for dep in dependencies if not TASK_ID_RE.match(str(dep))]
    if invalid:
        raise BBError(f"Invalid task dependency identifiers: {', '.join(map(str, invalid))}")
    if len(set(dependencies)) != len(dependencies):
        raise BBError("Task dependencies must not contain duplicates.")


def _append_proposal_md(root: Path, state: dict[str, Any], text: str) -> None:
    path = root / state["report_path"]
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def create_proposal(
    root: Path,
    agent_name: str,
    title: str,
    body: str,
    *,
    kind: str = "OTHER",
    task: str | None = None,
    source_note: str | None = None,
    task_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not title.strip() or not body.strip():
        raise BBError("Proposal title and body are required.")
    if task and task not in parse_task_index(root):
        raise BBError(f"Unknown task: {task}")
    if kind.upper() == "NEW_TASK":
        if not task_spec:
            raise BBError("NEW_TASK proposal requires structured task_spec metadata.")
        _validate_task_spec(task_spec)
    with locked(root):
        source_state = None
        if source_note:
            _, source_state_path = note_paths(root, source_note)
            source_state = read_json(source_state_path)
            if not source_state:
                raise BBError(f"Unknown note: {source_note}")
        proposal_id = _allocate_id_unlocked(root, "proposal", "P", 4)
        created = iso_now()
        report_name = f"{proposal_id}-{slugify(title)}.md"
        report_path = Path("reports") / report_name
        state = {
            "id": proposal_id,
            "title": title.strip(),
            "kind": kind.upper(),
            "author": agent_name,
            "created": created,
            "status": "OPEN",
            "revision": 1,
            "task": task,
            "source_note": source_note,
            "report_path": str(report_path),
            "stances": {},
            "objections": {},
            "amendments": [],
            "task_spec": task_spec,
            "distillation_status": "NOT_APPLICABLE" if kind.upper() == "NEW_TASK" else "NOT_STARTED",
        }
        markdown = (
            "---\n"
            f"id: {proposal_id}\n"
            f"kind: {state['kind']}\n"
            f"author: {agent_name}\n"
            f"created: {created}\n"
            f"task: {task or '—'}\n"
            f"source_note: {source_note or '—'}\n"
            "status: OPEN\n"
            "revision: 1\n"
            "---\n\n"
            f"# {proposal_id} — {title.strip()}\n\n"
            "## Proposal\n\n"
            f"{body.strip()}\n\n"
            "## Deliberation log\n\n"
        )
        atomic_write_text(root / report_path, markdown)
        atomic_write_json(proposal_state_path(root, proposal_id), state)
        append_event_unlocked(
            root,
            "PROPOSAL_CREATED",
            agent_name,
            proposal=proposal_id,
            kind=state["kind"],
            task=task,
            source_note=source_note,
        )
        if source_state and source_state.get("status") == "OPEN":
            source_state["status"] = "CONSUMED"
            source_state["consumed_by"] = proposal_id
            source_state["consumed_at"] = iso_now()
            source_state["consumed_by_agent"] = agent_name
            _, source_state_path = note_paths(root, source_note)
            atomic_write_json(source_state_path, source_state)
            source_md, _ = note_paths(root, source_note)
            update_frontmatter_field(source_md, "status", "CONSUMED")
            with source_md.open("a", encoding="utf-8") as handle:
                handle.write(f"## Consumed\n\n- By: `{proposal_id}`\n- Agent: {agent_name}\n- At: {source_state['consumed_at']}\n")
            append_event_unlocked(root, "NOTE_CONSUMED", agent_name, note=source_note, consumed_by=proposal_id)
        return state


def list_proposals(root: Path, *, status: str | None = None) -> list[dict[str, Any]]:
    ensure_layout(root)
    proposals: list[dict[str, Any]] = []
    for path in sorted((bb_dir(root) / "proposals").glob("P*.json")):
        state = read_json(path)
        if not state:
            continue
        if status and state.get("status") != status:
            continue
        proposals.append(state)
    return proposals


def set_stance(root: Path, proposal_id: str, agent_name: str, stance: str, comment: str | None = None) -> dict[str, Any]:
    stance = stance.upper()
    if stance not in {"SUPPORT", "NEUTRAL", "CHALLENGE"}:
        raise BBError(f"Invalid stance: {stance}")
    with locked(root):
        path = proposal_state_path(root, proposal_id)
        state = read_json(path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") != "OPEN":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and no longer open for review.")
        stamp = iso_now()
        revision = int(state.get("revision", 1))
        state.setdefault("stances", {})[agent_name] = {
            "stance": stance,
            "ts": stamp,
            "comment": comment,
            "revision": revision,
        }
        atomic_write_json(path, state)
        _append_proposal_md(root, state, f"### {stamp} — {agent_name} — {stance}\n\n{comment or '—'}\n\n")
        append_event_unlocked(
            root,
            stance,
            agent_name,
            proposal=proposal_id,
            task=state.get("task"),
            revision=revision,
            comment=comment,
        )
        return state


def object_proposal(root: Path, proposal_id: str, agent_name: str, reason: str) -> tuple[dict[str, Any], str]:
    if not reason.strip():
        raise BBError("Hard objection requires a concrete reason.")
    with locked(root):
        path = proposal_state_path(root, proposal_id)
        state = read_json(path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") != "OPEN":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and no longer open for objection.")
        objection_id = _allocate_id_unlocked(root, "objection", "O", 4)
        stamp = iso_now()
        objection = {
            "id": objection_id,
            "author": agent_name,
            "reason": reason.strip(),
            "created": stamp,
            "resolved": False,
            "resolved_at": None,
            "revision": int(state.get("revision", 1)),
        }
        state.setdefault("objections", {})[objection_id] = objection
        state.setdefault("stances", {})[agent_name] = {
            "stance": "HARD_OBJECTION",
            "ts": stamp,
            "comment": reason.strip(),
            "revision": int(state.get("revision", 1)),
        }
        atomic_write_json(path, state)
        _append_proposal_md(root, state, f"### {stamp} — {agent_name} — HARD_OBJECTION {objection_id}\n\n{reason.strip()}\n\n")
        append_event_unlocked(
            root,
            "HARD_OBJECTION",
            agent_name,
            proposal=proposal_id,
            objection=objection_id,
            task=state.get("task"),
            revision=int(state.get("revision", 1)),
            reason=reason.strip(),
        )
        return state, objection_id


def _find_objection(root: Path, objection_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    for path in sorted((bb_dir(root) / "proposals").glob("P*.json")):
        state = read_json(path)
        if state and objection_id in state.get("objections", {}):
            return path, state, state["objections"][objection_id]
    raise BBError(f"Unknown objection: {objection_id}")


def resolve_objection(root: Path, objection_id: str, agent_name: str, comment: str | None = None) -> dict[str, Any]:
    with locked(root):
        path, state, objection = _find_objection(root, objection_id)
        if objection.get("resolved"):
            return state
        if objection.get("author") != agent_name:
            raise BBError(
                f"Only the objection author ({objection.get('author')}) may resolve {objection_id} in the MVP."
            )
        stamp = iso_now()
        objection["resolved"] = True
        objection["resolved_at"] = stamp
        objection["resolution_comment"] = comment
        # After resolving, the author's blocking stance becomes neutral unless they explicitly choose another stance later.
        state.setdefault("stances", {})[agent_name] = {
            "stance": "NEUTRAL",
            "ts": stamp,
            "comment": comment,
            "revision": int(state.get("revision", 1)),
        }
        atomic_write_json(path, state)
        _append_proposal_md(root, state, f"### {stamp} — {agent_name} — RESOLVED {objection_id}\n\n{comment or 'Resolved.'}\n\n")
        append_event_unlocked(
            root,
            "OBJECTION_RESOLVED",
            agent_name,
            proposal=state["id"],
            objection=objection_id,
            task=state.get("task"),
            comment=comment,
        )
        return state


def amend_proposal(root: Path, proposal_id: str, agent_name: str, text: str) -> dict[str, Any]:
    if not text.strip():
        raise BBError("Amendment text cannot be empty.")
    with locked(root):
        path = proposal_state_path(root, proposal_id)
        state = read_json(path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") != "OPEN":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and cannot be amended.")
        revision = int(state.get("revision", 1)) + 1
        state["revision"] = revision
        amendment = {"ts": iso_now(), "agent": agent_name, "text": text.strip(), "revision": revision}
        state.setdefault("amendments", []).append(amendment)
        atomic_write_json(path, state)
        update_frontmatter_field(root / state["report_path"], "revision", str(revision))
        _append_proposal_md(
            root,
            state,
            f"### {amendment['ts']} — {agent_name} — AMENDMENT (revision {revision})\n\n{text.strip()}\n\n"
            "Previous reviewer stances do not count for this revision and must be re-recorded.\n\n",
        )
        append_event_unlocked(
            root,
            "PROPOSAL_AMENDED",
            agent_name,
            proposal=proposal_id,
            task=state.get("task"),
            revision=revision,
        )
        return state


def amend_task_proposal(
    root: Path,
    proposal_id: str,
    agent_name: str,
    *,
    title: str | None = None,
    objective: str | None = None,
    priority: str | None = None,
    dependencies: list[str] | None = None,
    acceptance: list[str] | None = None,
    verification: list[str] | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    """Apply a structured revision to a NEW_TASK proposal and invalidate old review stances."""
    with locked(root):
        path = proposal_state_path(root, proposal_id)
        state = read_json(path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") != "OPEN":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and cannot be amended.")
        if state.get("kind") != "NEW_TASK":
            raise BBError("Structured task amendments are only valid for NEW_TASK proposals.")
        if all(value is None for value in (title, objective, priority, dependencies, acceptance, verification)):
            raise BBError("At least one structured task field must be changed.")

        spec = dict(state.get("task_spec") or {})
        changes: dict[str, Any] = {}
        for key, value in (
            ("title", title),
            ("objective", objective),
            ("priority", priority),
            ("dependencies", dependencies),
            ("acceptance", acceptance),
            ("verification", verification),
        ):
            if value is not None:
                spec[key] = value
                changes[key] = value
        _validate_task_spec(spec)

        revision = int(state.get("revision", 1)) + 1
        state["revision"] = revision
        state["task_spec"] = spec
        amendment = {
            "ts": iso_now(),
            "agent": agent_name,
            "revision": revision,
            "type": "STRUCTURED_TASK_REVISION",
            "changes": changes,
            "text": comment,
        }
        state.setdefault("amendments", []).append(amendment)
        if title is not None:
            state["title"] = title.strip()
        atomic_write_json(path, state)
        report = root / state["report_path"]
        update_frontmatter_field(report, "revision", str(revision))
        rendered = json.dumps(changes, indent=2, sort_keys=True)
        _append_proposal_md(
            root,
            state,
            f"### {amendment['ts']} — {agent_name} — STRUCTURED TASK REVISION {revision}\n\n"
            f"```json\n{rendered}\n```\n\n"
            + (f"{comment.strip()}\n\n" if comment and comment.strip() else "")
            + "Previous reviewer stances do not count for this revision and must be re-recorded.\n\n",
        )
        append_event_unlocked(
            root,
            "PROPOSAL_TASK_REVISED",
            agent_name,
            proposal=proposal_id,
            revision=revision,
            changes=sorted(changes),
        )
        return state


def withdraw_proposal(root: Path, proposal_id: str, agent_name: str, reason: str | None = None) -> dict[str, Any]:
    with locked(root):
        path = proposal_state_path(root, proposal_id)
        state = read_json(path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") != "OPEN":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and cannot be withdrawn.")
        if state.get("author") != agent_name:
            raise BBError(f"Only proposal author {state.get('author')} may withdraw {proposal_id}.")
        stamp = iso_now()
        state["status"] = "WITHDRAWN"
        state["withdrawn_at"] = stamp
        state["withdrawn_by"] = agent_name
        state["withdrawal_reason"] = reason
        atomic_write_json(path, state)
        update_frontmatter_field(root / state["report_path"], "status", "WITHDRAWN")
        _append_proposal_md(
            root,
            state,
            f"## Withdrawal\n\n- Status: WITHDRAWN\n- By: {agent_name}\n- At: {stamp}\n"
            + (f"- Reason: {reason}\n" if reason else ""),
        )
        append_event_unlocked(root, "PROPOSAL_WITHDRAWN", agent_name, proposal=proposal_id, reason=reason)
        return state


def supersede_proposal(
    root: Path,
    proposal_id: str,
    accepted_proposal_id: str,
    agent_name: str,
    reason: str | None = None,
) -> dict[str, Any]:
    with locked(root):
        if proposal_id == accepted_proposal_id:
            raise BBError("A proposal cannot supersede itself.")
        path = proposal_state_path(root, proposal_id)
        state = read_json(path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") != "OPEN":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and cannot be superseded.")
        accepted = read_json(proposal_state_path(root, accepted_proposal_id))
        if not accepted:
            raise BBError(f"Unknown superseding proposal: {accepted_proposal_id}")
        if accepted.get("status") != "ACCEPTED":
            raise BBError(f"Superseding proposal {accepted_proposal_id} must already be ACCEPTED.")
        stamp = iso_now()
        state["status"] = "SUPERSEDED"
        state["superseded_at"] = stamp
        state["superseded_by"] = accepted_proposal_id
        state["superseded_by_agent"] = agent_name
        state["supersession_reason"] = reason
        atomic_write_json(path, state)
        update_frontmatter_field(root / state["report_path"], "status", "SUPERSEDED")
        _append_proposal_md(
            root,
            state,
            f"## Superseded\n\n- Status: SUPERSEDED\n- By accepted proposal: `{accepted_proposal_id}`\n"
            f"- Recorded by: {agent_name}\n- At: {stamp}\n"
            + (f"- Reason: {reason}\n" if reason else ""),
        )
        append_event_unlocked(
            root,
            "PROPOSAL_SUPERSEDED",
            agent_name,
            proposal=proposal_id,
            superseded_by=accepted_proposal_id,
            reason=reason,
        )
        return state


def consensus_state(state: dict[str, Any]) -> dict[str, Any]:
    author = state.get("author")
    stances = state.get("stances", {})
    revision = int(state.get("revision", 1))
    current_stances = {
        name: value
        for name, value in stances.items()
        if int(value.get("revision", 1)) == revision
    }
    reviewers = {name for name in current_stances if name != author}
    supporters = {
        name
        for name, value in current_stances.items()
        if name != author and value.get("stance") == "SUPPORT"
    }
    unresolved = [
        objection
        for objection in state.get("objections", {}).values()
        if not objection.get("resolved")
    ]
    result = {
        "reviewers": len(reviewers),
        "supporters": len(supporters),
        "unresolved_objections": len(unresolved),
        "reviewer_agents": sorted(reviewers),
        "supporter_agents": sorted(supporters),
        "objection_ids": sorted(o["id"] for o in unresolved),
        "revision": revision,
    }
    result["ready"] = (
        result["reviewers"] >= 3
        and result["supporters"] >= 2
        and result["unresolved_objections"] == 0
    )
    return result


def _insert_task_row_unlocked(root: Path, task: dict[str, Any]) -> None:
    path = root / "PRD.md"
    text = path.read_text(encoding="utf-8")
    if TASK_INDEX_START not in text or TASK_INDEX_END not in text:
        raise BBError("PRD.md is missing Blackboard task-index markers.")
    deps = ", ".join(task.get("dependencies", [])) or "—"
    row = (
        f"| {task['id']} | {task['title']} | PLANNED | {task['priority']} | {deps} | "
        f"[{task['id']}](prd/{task['id']}.md) | "
        f"[PROGRESS-{task['id']}](progress/PROGRESS-{task['id']}.md) |\n"
    )
    before, after = text.split(TASK_INDEX_END, 1)
    if not before.endswith("\n"):
        before += "\n"
    atomic_write_text(path, before + row + TASK_INDEX_END + after)


def _render_new_task_spec(
    task_id: str,
    spec: dict[str, Any],
    source_proposal: str,
    source_report_path: str,
) -> str:
    acceptance = spec.get("acceptance") or ["The task objective is demonstrably satisfied."]
    verification = spec.get("verification") or ["Perform an explicit verification appropriate to the task before completion."]
    acceptance_lines = "\n".join(f"  - {item}" for item in acceptance)
    verification_lines = "\n".join(f"  - {item}" for item in verification)
    return f"""# {task_id} — {spec['title']}

## Metadata

- Last specification update: {utc_now().date().isoformat()}
- Source proposal: [{source_proposal}](../{source_report_path})

## Objective

{spec['objective']}

## Scope

### In scope

- Deliver the accepted objective and acceptance criteria from {source_proposal}.

### Out of scope

- Work not required by the accepted proposal or later canonical amendments.

## Context

This macro-task was materialized mechanically from accepted Blackboard proposal `{source_proposal}`.

## Contracts and interfaces

- Preserve project-wide invariants in `PRD.md`.
- Any material scope/architecture change discovered during execution must return through the proposal loop.

## Sub-tasks

### {task_id}-SUB001 — Deliver accepted objective

- Goal: {spec['objective']}
- Dependencies: —
- Acceptance criteria:
{acceptance_lines}
- Verification:
{verification_lines}
- Reports:
  - Add links only to reports that actually exist.

## Risks

- To be refined by the task owner if execution reveals material task-specific risks.

## Open questions

- None recorded at materialization time.
"""


def _render_new_task_progress(task_id: str, spec: dict[str, Any]) -> str:
    today = utc_now().date().isoformat()
    return f"""# PROGRESS-{task_id} — {spec['title']}

## Current state

- Status: PLANNED
- Active sub-task: —
- Blocked by: —
- Last update: {today}

## Sub-task status

| ID | Status | Last update | Report |
|---|---|---|---|
| {task_id}-SUB001 | PLANNED | — | — |

## Current blockers

- None.

## Decisions still relevant

- None beyond the canonical specification.

## Recent events

### {today} — Task materialized

- Created from an accepted Blackboard `NEW_TASK` proposal.

## Next action

- Claim the task, inspect the accepted proposal/context, and start `{task_id}-SUB001` when dependencies are satisfied.
"""


def consolidate_proposal(root: Path, proposal_id: str, agent_name: str) -> dict[str, Any]:
    with locked(root):
        state_path = proposal_state_path(root, proposal_id)
        state = read_json(state_path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") == "ACCEPTED":
            return state
        if state.get("status") != "OPEN":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and cannot be consolidated.")
        consensus = consensus_state(state)
        if not consensus["ready"]:
            raise BBError(
                f"Proposal {proposal_id} is not ready: reviewers={consensus['reviewers']}/3, "
                f"supporters={consensus['supporters']}/2, "
                f"unresolved_objections={consensus['unresolved_objections']}."
            )

        materialized_task = None
        if state.get("kind") == "NEW_TASK":
            spec = state.get("task_spec") or {}
            _validate_task_spec(spec)
            tasks = parse_task_index(root)
            dependencies = spec.get("dependencies") or []
            unknown = [dep for dep in dependencies if dep not in tasks]
            if unknown:
                raise BBError(f"NEW_TASK proposal references unknown dependencies: {', '.join(unknown)}")
            materialized_task = _allocate_id_unlocked(root, "task", "T", 3)
            task_payload = {
                "id": materialized_task,
                "title": spec["title"],
                "priority": spec["priority"],
                "dependencies": dependencies,
            }
            spec_path = root / "prd" / f"{materialized_task}.md"
            progress_path = root / "progress" / f"PROGRESS-{materialized_task}.md"
            if spec_path.exists() or progress_path.exists():
                raise BBError(f"Refusing to reuse existing task identifier {materialized_task}.")
            atomic_write_text(
                spec_path,
                _render_new_task_spec(materialized_task, spec, proposal_id, state["report_path"]),
            )
            atomic_write_text(progress_path, _render_new_task_progress(materialized_task, spec))
            _insert_task_row_unlocked(root, task_payload)

        stamp = iso_now()
        state["status"] = "ACCEPTED"
        state["accepted_at"] = stamp
        state["accepted_by"] = agent_name
        state["consensus_at_acceptance"] = consensus
        state["accepted_revision"] = int(state.get("revision", 1))
        if materialized_task:
            state["materialized_task"] = materialized_task
            state["distillation_status"] = "COMPLETE"
            state["distilled_at"] = stamp
            state["distilled_by"] = agent_name
            state["distilled_into"] = [
                "PRD.md",
                f"prd/{materialized_task}.md",
                f"progress/PROGRESS-{materialized_task}.md",
            ]
        else:
            state["distillation_status"] = "PENDING"
        atomic_write_json(state_path, state)
        update_frontmatter_field(root / state["report_path"], "status", "ACCEPTED")
        _append_proposal_md(
            root,
            state,
            f"## Consolidation\n\n- Status: ACCEPTED\n- By: {agent_name}\n- At: {stamp}\n"
            + (f"- Materialized task: `{materialized_task}`\n" if materialized_task else "- Canonical distillation required: yes\n"),
        )
        append_event_unlocked(
            root,
            "PROPOSAL_CONSOLIDATED",
            agent_name,
            proposal=proposal_id,
            kind=state.get("kind"),
            task=state.get("task"),
            materialized_task=materialized_task,
        )
        if materialized_task:
            append_event_unlocked(
                root,
                "TASK_CREATED",
                agent_name,
                task=materialized_task,
                source_proposal=proposal_id,
            )
        else:
            append_event_unlocked(
                root,
                "CANONICAL_DISTILLATION_REQUIRED",
                agent_name,
                proposal=proposal_id,
                task=state.get("task"),
            )
        return state


def distill_proposal(
    root: Path,
    proposal_id: str,
    agent_name: str,
    canonical_refs: list[str],
    note: str | None = None,
) -> dict[str, Any]:
    """Close the accepted -> canonical-memory loop without judging semantic correctness."""
    if not canonical_refs:
        raise BBError("At least one canonical destination is required.")
    with locked(root):
        path = proposal_state_path(root, proposal_id)
        state = read_json(path)
        if not state:
            raise BBError(f"Unknown proposal: {proposal_id}")
        if state.get("status") != "ACCEPTED":
            raise BBError(f"Proposal {proposal_id} is {state.get('status')} and is not accepted.")
        if state.get("kind") == "NEW_TASK":
            raise BBError("NEW_TASK proposals are mechanically distilled during consolidation.")
        if state.get("distillation_status") == "COMPLETE":
            return state

        normalized: list[str] = []
        for ref in canonical_refs:
            rel = Path(ref)
            if rel.is_absolute() or ".." in rel.parts:
                raise BBError(f"Canonical destination must be a repository-relative path: {ref}")
            allowed = ref == "PRD.md" or (len(rel.parts) == 2 and rel.parts[0] == "prd" and TASK_ID_RE.match(rel.stem))
            if not allowed:
                raise BBError(
                    f"Canonical destination must be PRD.md or prd/Txxx.md, not {ref}."
                )
            target = root / rel
            if not target.exists():
                raise BBError(f"Canonical destination does not exist: {ref}")
            if len(rel.parts) == 2 and rel.parts[0] == "prd":
                task_id = rel.stem
                scoped_task = state.get("task")
                if scoped_task and task_id != scoped_task:
                    raise BBError(
                        f"Proposal {proposal_id} is scoped to {scoped_task} and cannot be distilled into {ref}."
                    )
                claim = get_claim(root, task_id)
                if not claim or claim.get("agent") != agent_name:
                    owner = claim.get("agent") if claim else None
                    detail = f"owned by {owner}" if owner else "not currently claimed"
                    raise BBError(
                        f"Cannot attest distillation into {ref}: {task_id} is {detail}. "
                        "Canonical task writes require the caller's live claim."
                    )
            normalized.append(str(rel))

        stamp = iso_now()
        state["distillation_status"] = "COMPLETE"
        state["distilled_at"] = stamp
        state["distilled_by"] = agent_name
        state["distilled_into"] = sorted(set(normalized))
        state["distillation_note"] = note
        atomic_write_json(path, state)
        _append_proposal_md(
            root,
            state,
            "## Canonical distillation\n\n"
            "- Status: COMPLETE\n"
            f"- By: {agent_name}\n"
            f"- At: {stamp}\n"
            f"- Into: {', '.join(f'`{item}`' for item in state['distilled_into'])}\n"
            + (f"- Note: {note}\n" if note else ""),
        )
        append_event_unlocked(
            root,
            "PROPOSAL_DISTILLED",
            agent_name,
            proposal=proposal_id,
            canonical_refs=state["distilled_into"],
            note=note,
        )
        return state


def history_for_ref(root: Path, ref: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for event in read_events(root):
        if any(value == ref for key, value in event.items() if key != "ts"):
            matches.append(event)
    return matches


def contributions_for_agent(root: Path, agent_name: str) -> list[dict[str, Any]]:
    return [event for event in read_events(root) if event.get("agent") == agent_name]


def check_consistency(root: Path) -> list[str]:
    issues: list[str] = []
    try:
        tasks = parse_task_index(root)
    except BBError as exc:
        return [str(exc)]
    for task_id, task in tasks.items():
        if task.get("status") not in VALID_STATUSES:
            issues.append(f"{task_id}: invalid status {task.get('status')}")
        if task.get("priority") not in VALID_PRIORITIES:
            issues.append(f"{task_id}: invalid priority {task.get('priority')}")
        spec = root / "prd" / f"{task_id}.md"
        progress = root / "progress" / f"PROGRESS-{task_id}.md"
        if not spec.exists():
            issues.append(f"{task_id}: missing {spec.relative_to(root)}")
        if not progress.exists():
            issues.append(f"{task_id}: missing {progress.relative_to(root)}")
            continue
        try:
            status = progress_status(root, task_id)
        except BBError as exc:
            issues.append(str(exc))
            continue
        if status != task["status"]:
            issues.append(f"{task_id}: root status {task['status']} != progress status {status}")
        for dep in task.get("dependencies", []):
            if not TASK_ID_RE.match(dep):
                issues.append(f"{task_id}: invalid dependency identifier {dep}")
            if dep not in tasks:
                issues.append(f"{task_id}: unknown dependency {dep}")
            if dep == task_id:
                issues.append(f"{task_id}: task cannot depend on itself")
    for claim in list_claims(root):
        if claim.get("task") not in tasks:
            issues.append(f"live claim references unknown task {claim.get('task')}")
            continue
        if not claim.get("agent"):
            issues.append(f"live claim for {claim.get('task')} has no agent")
        status = tasks[claim["task"]]["status"]
        if status not in {"PLANNED", "IN_PROGRESS"}:
            issues.append(f"live claim for {claim['task']} exists while task status is {status}")

    for state_path in sorted((bb_dir(root) / "proposals").glob("P*.json")):
        state = read_json(state_path)
        if not state:
            issues.append(f"invalid or empty proposal state: {state_path.relative_to(root)}")
            continue
        proposal_id = state.get("id")
        if state.get("status") not in VALID_PROPOSAL_STATUSES:
            issues.append(f"{proposal_id}: invalid proposal status {state.get('status')}")
        report_path = root / str(state.get("report_path", ""))
        if not state.get("report_path") or not report_path.exists():
            issues.append(f"{proposal_id}: missing proposal report {state.get('report_path')}")
        elif report_path.exists():
            frontmatter = read_frontmatter_fields(report_path)
            if frontmatter.get("status") != state.get("status"):
                issues.append(
                    f"{proposal_id}: report status {frontmatter.get('status')} != state status {state.get('status')}"
                )
            if str(frontmatter.get("revision", "1")) != str(state.get("revision", 1)):
                issues.append(
                    f"{proposal_id}: report revision {frontmatter.get('revision', '1')} != state revision {state.get('revision', 1)}"
                )
        if state.get("kind") == "NEW_TASK" and state.get("status") == "ACCEPTED":
            materialized = state.get("materialized_task")
            if not materialized or materialized not in tasks:
                issues.append(f"{proposal_id}: accepted NEW_TASK has no valid materialized task")

    for state_path in sorted((bb_dir(root) / "notes").glob("N*.json")):
        state = read_json(state_path)
        if not state:
            issues.append(f"invalid or empty note state: {state_path.relative_to(root)}")
            continue
        note_id = state.get("id")
        md_path, _ = note_paths(root, str(note_id))
        if not md_path.exists():
            issues.append(f"{note_id}: missing note Markdown artifact")
            continue
        frontmatter = read_frontmatter_fields(md_path)
        if frontmatter.get("status") != state.get("status"):
            issues.append(
                f"{note_id}: Markdown status {frontmatter.get('status')} != state status {state.get('status')}"
            )

    events_path = bb_dir(root) / "events.jsonl"
    if events_path.exists():
        for line_no, raw in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                json.loads(raw)
            except json.JSONDecodeError:
                issues.append(f"events.jsonl:{line_no}: malformed JSON event")

    counters = read_json(bb_dir(root) / "counters.json", {}) or {}
    inferred = _infer_counters(root)
    for kind, observed in inferred.items():
        persisted = int(counters.get(kind, 0))
        if persisted < observed:
            issues.append(f"counter {kind}={persisted} is behind observed stable ID {observed}")
    return issues
