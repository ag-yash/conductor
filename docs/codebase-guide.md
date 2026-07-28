# How to read the Conductor codebase

This is a learning guide, not a replacement for the technical design documents. Read it when you want to understand **why files exist**, **where a feature belongs**, and **how a request travels through the system**.

## Start here

Conductor has one simple job: accept AI work, decide which local worker should do it, and remember what happened even after a restart.

For M4, the easiest story is:

```text
Client submits a job
        ↓
The job is saved as queued in SQLite
        ↓
A worker asks for work
        ↓
Conductor compares workers and records its reason
        ↓
The selected worker gets a lease and finishes the job
```

## The four layers

| Layer | Plain-English responsibility | Example |
| --- | --- | --- |
| `api/` | Receives HTTP requests and returns HTTP responses | `POST /jobs` |
| `services/` | Coordinates one business action | “register this worker” |
| `domain/` and `scheduler/` | Holds rules that must stay true | “a running job may succeed” |
| `storage/` and `models/` | Reads/writes durable SQLite data | save a job or worker |

The important rule is: **an API route should not contain business rules or SQL.** It validates input, calls a service, and converts the result to a response. This keeps the same rules reusable by a future CLI or dashboard.

## A feature, end to end

Use M4 scheduling as the example. Read these files in this order:

1. [`scheduler/policy.py`](../backend/src/conductor/scheduler/policy.py) — the pure decision rule. It does not know about HTTP or SQLite.
2. [`services/workers.py`](../backend/src/conductor/services/workers.py) — obtains a snapshot from storage, calls the policy, and persists the outcome.
3. [`storage/repositories.py`](../backend/src/conductor/storage/repositories.py) — turns database rows into Python objects and back.
4. [`api/workers.py`](../backend/src/conductor/api/workers.py) — exposes worker polling through HTTP.
5. [`api/jobs.py`](../backend/src/conductor/api/jobs.py) — lets an operator inspect the recorded scheduling explanation.
6. [`tests/test_scheduling_api.py`](../tests/test_scheduling_api.py) — proves the user-visible behavior.

That order is useful for every future feature: start with the rule, then the use case, then persistence and HTTP, then the test.

## Important code patterns

### Domain objects are immutable

`Job`, `Worker`, and `ExecutionAttempt` are frozen dataclasses. A method like `job.assign(...)` returns a **new** job rather than changing the old one in place.

Why? It makes transitions explicit and gives us a version number for safe concurrent updates.

### Services own transactions

For an operation such as leasing a job, the service uses one `UnitOfWork`:

```text
create attempt + change job status + save scheduling explanation + commit
```

They either all succeed together or none of them do. That is what prevents two workers from both believing they own the same job.

### Repository interfaces separate “what” from “how”

`services/ports.py` says what storage operations the application needs. `storage/repositories.py` provides the SQLite version. This means the service code does not depend directly on SQLModel.

### Scheduler policy stays pure

`PlacementPolicy.decide()` accepts a job and worker snapshots, then returns a `PlacementDecision`. It does not write to the database. A pure function is easy to test because the same input always gives the same output.

## M1–M4 map

| Milestone | Main idea | Read first |
| --- | --- | --- |
| M1 | API process starts safely | `main.py`, `api/health.py` |
| M2 | Jobs survive restart | `domain/job.py`, `services/jobs.py` |
| M3 | Workers safely lease and finish jobs | `domain/worker.py`, `services/workers.py` |
| M4 | Placement decisions are fair and explainable | `scheduler/policy.py` |

## How we will update this guide

Every milestone will add:

1. A short explanation of the new idea in this file.
2. A “read these files in this order” list.
3. Comments around the tricky code paths—not comments that merely repeat the code.
4. A plain-language API or demo document when the feature is visible to a user.

If you want personal scratch notes, create a local `notes/` directory and add it to your own global Git ignore file. The guide above should stay committed because it is part of making Conductor understandable as an open-source project.
