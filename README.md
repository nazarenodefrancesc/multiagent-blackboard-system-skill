# Blackboard Collaboration Skill

A controller-free Blackboard collaboration layer for heterogeneous AI agents sharing one Linux repository.

It is designed to sit on top of the [**Scalable Ralph Loop Patch**](https://github.com/nazarenodefrancesc/scalable-ralph-loop-patch) memory model:

```text
PRD.md                     global routing context
prd/Txxx.md                canonical task specification
progress/PROGRESS-Txxx.md  bounded hot state
reports/                   cold evidence and proposal artifacts
Git                        provenance
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

You do not need a dedicated multi-agent framework to use this system.

Start from whatever agents you already have.

Typical setups include:

- one coding agent such as Claude Code, OpenClaw, Hermes, Codex, or another agent that can spawn sub-agents;
- several independent agents already running on the same machine;
- a mix of heterogeneous agents using different models or frameworks.

The only requirement is that all participating agents can access the same Git repository and can execute shell commands.

### 1. Make the skill available to your agents

Clone this repository somewhere accessible to the agents, or install/copy `SKILL.md` into the skill system used by your agent framework.

The important part is that every participating agent receives the same **Blackboard Collaboration** instructions.

The repository containing the actual project to be solved should use the [**Scalable Ralph Loop Patch**](https://github.com/nazarenodefrancesc/scalable-ralph-loop-patch) memory structure:

```text
PRD.md
prd/
progress/
reports/
```

and the Blackboard runtime state:

```text
.blackboard/
```

The `bb` CLI can either be installed or invoked directly from this repository.

### 2. Give all agents the same project brief

For example:

> Build a web application for managing shared tasks, with an API, browser UI, persistence, tests, logging, Docker packaging, and documentation.
>
> Use the Blackboard Collaboration skill. Work collaboratively through the shared repository. Do not assume a predefined role. Read the Blackboard before acting, contribute where useful, and re-read shared state after meaningful changes.

Do **not** manually assign roles such as:

```text
Agent 1 = backend
Agent 2 = frontend
Agent 3 = reviewer
```

unless you explicitly want a role-based architecture.

The Blackboard approach is designed to let useful specialization emerge from the state of the shared problem.

### 3. Start the agents

There are two common ways to do this.

#### Option A — One parent agent that can spawn sub-agents

If your preferred agent can create parallel sub-agents, ask it to start several independent workers on the same repository.

For example:

> Spawn 4 independent agents.
>
> Give each agent the Blackboard Collaboration skill and the same project brief.
>
> All agents must work on the same repository and coordinate only through the Blackboard protocol.
>
> Do not create a manager/planner agent. Each agent should independently inspect shared state and decide whether it can contribute useful work.

The parent process is only responsible for launching the agents.

It should **not** become the semantic orchestrator of the project.

Conceptually:

```text
                    your agent
                  /    |    |    \
                 /     |    |     \
             agent A agent B agent C agent D
                 \      |      /
                  \     |     /
                   BLACKBOARD
```

#### Option B — Several agents already running

If you already have multiple agents active, point all of them at the same repository and give each one:

1. the same project brief;
2. the Blackboard Collaboration skill;
3. a unique stable identity.

For example:

```text
hermes-01
openclaw-01
claude-01
prime-01
```

Each agent should then independently enter the Blackboard loop:

```text
READ
  ↓
ORIENT
  ↓
CONTRIBUTE
  ↓
UPDATE SHARED STATE
  ↓
RE-READ
```

No agent needs to know in advance what the others will do.

### 4. Let the agents bootstrap the project collaboratively

The initial project may contain little more than:

```text
PRD.md
```

with the original brief and no canonical tasks yet.

That is intentional.

During cold start, agents should:

```text
brief
  ↓
observations
  ↓
notes / reports / proposals
  ↓
cross-agent review
  ↓
consensus
  ↓
canonical Txxx tasks
  ↓
execution
```

The first task decomposition therefore emerges collaboratively instead of being generated by a central planner.

Agents themselves will invoke commands such as:

```bash
bb status
bb note ...
bb propose-task ...
bb support ...
bb challenge ...
bb consolidate ...
bb claim T003
bb heartbeat T003
bb complete T003
```

These are **agent coordination primitives**.

They are normally not commands the human operator needs to execute manually.

### 5. Observe rather than orchestrate

Once the agents are running, the human operator can mostly observe the shared state.

Useful inspection points are:

```text
PRD.md
    current canonical project map

progress/
    current execution state

.blackboard/notes/
    weak observations and discoveries

reports/
    investigations, reviews, and proposals

.blackboard/events.jsonl
    collaboration audit trail

Git history
    implementation provenance
```

The key behavior to look for is not simply parallel task execution.

It is information crossing agent boundaries:

```text
Agent A discovers something
        ↓
      NOTE
        ↓
Agent B interprets it
        ↓
    PROPOSAL
        ↓
Agent C implements the resulting task
```

That is the core Blackboard collaboration loop.

### Minimal mental model

If you already have agents, the setup is simply:

```text
your existing agents
        +
same repository
        +
same Blackboard skill
        +
unique identities
        ↓
multi-agent Blackboard
```

No database.

No central planner.

No mandatory agent framework.

No dedicated manager agent.

The agents coordinate by continuously reading and enriching the same shared project state.

## What agents do at runtime

Agents use `bb` themselves as the coordination mechanism.

For example, an agent may claim a task:

```bash
./bin/bb claim T003
./bin/bb heartbeat T003
# work, verify, update canonical task/progress
./bin/bb release T003
```

leave a weak observation:

```bash
./bin/bb note --task T003 --type warning \
  "The external API appears rate-limited per API key."
```

or create and deliberate a proposal:

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

This repository is itself managed as a PRD-driven project following the [**Scalable Ralph Loop Patch**](https://github.com/nazarenodefrancesc/scalable-ralph-loop-patch) approach. See `PRD.md`, `prd/`, `progress/`, and the included Git history.

## MVP limitations intentionally left for pilot evidence

- claim ownership does not lock arbitrary source-code paths;
- agents share a working tree unless the host framework gives each agent its own worktree;
- no watcher wakes idle agents automatically;
- non-`NEW_TASK` accepted proposals are not semantically applied by `bb`; an agent edits canonical memory and `bb distill` records where that decision was incorporated;
- consensus thresholds are fixed defaults in this MVP.

These are explicit pilot targets, not hidden assumptions.
