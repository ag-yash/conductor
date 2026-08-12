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

## Repository map

```text
Conductor/
├── backend/
│   ├── migrations/          versioned SQLite schema changes
│   └── src/conductor/
│       ├── api/             HTTP request and response boundary
│       ├── config/          validated environment settings
│       ├── core/            logging and request context
│       ├── domain/          Job, Worker, and Attempt rules
│       ├── models/          SQLModel database record shapes
│       ├── scheduler/       pure placement policy
│       ├── services/        use cases and repository interfaces
│       ├── storage/         SQLite repositories and transactions
│       ├── runtime/         adapters and process-local model loading
│       └── workers/         local worker process code as it grows
├── docs/                    product, learning, and design documents
├── tests/                   unit and integration tests
├── pyproject.toml           package, dependencies, and tool settings
├── Makefile                 common developer commands
└── docker-compose.yml       reproducible process setup
```

Do not try to read every file from top to bottom. Pick one behavior and trace it across layers.

## A feature, end to end

Use M4 scheduling as the example. Read these files in this order:

1. [`scheduler/policy.py`](../backend/src/conductor/scheduler/policy.py) — the pure decision rule. It does not know about HTTP or SQLite.
2. [`services/workers.py`](../backend/src/conductor/services/workers.py) — obtains a snapshot from storage, calls the policy, and persists the outcome.
3. [`storage/repositories.py`](../backend/src/conductor/storage/repositories.py) — turns database rows into Python objects and back.
4. [`api/workers.py`](../backend/src/conductor/api/workers.py) — exposes worker polling through HTTP.
5. [`api/jobs.py`](../backend/src/conductor/api/jobs.py) — lets an operator inspect the recorded scheduling explanation.
6. [`tests/test_scheduling_api.py`](../tests/test_scheduling_api.py) — proves the user-visible behavior.

That order is useful for every future feature: start with the rule, then the use case, then persistence and HTTP, then the test.

## Trace 1: submitting a job

```text
POST /jobs
   ↓ api/jobs.py validates JSON and header
JobService.submit()
   ↓ computes canonical request hash
Job.create()
   ↓ creates a valid immutable queued job
SqlJobRepository.add()
   ↓ translates domain object to JobRecord
SQLite transaction commits
   ↓
JobResponse returns JSON
```

The API knows HTTP. The domain knows legal state. The repository knows SQL. The service connects them.

## Trace 2: a worker receives a job

```text
POST /workers/{id}/leases/next
   ↓
WorkerService verifies the current process-instance ID
   ↓
Repositories read queued jobs, workers, and active attempts
   ↓
PlacementPolicy returns a selected worker plus explanations
   ↓
Service creates attempt + assigns job + stores decision
   ↓
One transaction commits all three writes
```

The transaction is the key correctness boundary. If only one of those writes were saved, the database could contradict itself.

## Trace 3: a worker executes a model

```text
POST /workers/{id}/attempts/{attempt}/execute
   ↓
WorkerService verifies the current worker process and running attempt
   ↓
Model definition is loaded from SQLite
   ↓
RuntimeManager finds or loads the adapter's model
   ↓
Adapter invokes the model-specific runtime
   ↓
Job result is saved and attempt becomes succeeded
```

The important separation is that `WorkerService` coordinates the use case, while
`RuntimeManager` owns the short-lived loaded-model cache. The service does not
know whether the model is fixture, Ollama, or a future ONNX runtime.

After execution, `WorkerService` also copies the manager's latest residency
snapshot into SQLite. This gives operators a durable view without pretending that
SQLite owns the model's in-memory object.

To evict an idle model:

```text
POST /workers/{id}/evict-idle
   ↓
RuntimeManager checks last_used_at + timeout
   ↓
Adapter unloads eligible models
   ↓
WorkerService deletes only successfully unloaded snapshots
```

## Trace 4: benchmarking a warm model

```text
POST /workers/{id}/benchmarks
   ↓
WorkerService validates the worker capability and model definition
   ↓
RuntimeManager performs unmeasured warmups
   ↓
RuntimeManager performs timed samples
   ↓
BenchmarkSummary calculates min, mean, max, and total wall-clock time
   ↓
SQLite stores one immutable summary for later comparison
```

The benchmark does not create a normal `Job` or `ExecutionAttempt`. It is an
operator measurement, not user-submitted work waiting in the queue. It still uses
the same trusted model definition and runtime adapter, so it measures the actual
execution path rather than a copy of that logic.

## Important code patterns

### Domain objects are immutable

`Job`, `Worker`, and `ExecutionAttempt` are frozen dataclasses. A method like `job.assign(...)` returns a **new** job rather than changing the old one in place.

Why? It makes transitions explicit and gives us a version number for safe concurrent updates.

Example:

```python
assigned = queued.assign(attempt_id)
```

After this line, `queued` still represents the old snapshot and `assigned` is the new version. The repository updates the database using `queued.version` as the expected value.

### Services own transactions

For an operation such as leasing a job, the service uses one `UnitOfWork`:

```text
create attempt + change job status + save scheduling explanation + commit
```

They either all succeed together or none of them do. That is what prevents two workers from both believing they own the same job.

### Repository interfaces separate “what” from “how”

`services/ports.py` says what storage operations the application needs. `storage/repositories.py` provides the SQLite version. This means the service code does not depend directly on SQLModel.

This is dependency inversion in practical form:

```text
High-level JobService → JobRepository interface ← SQLite implementation
```

The arrow of source-code dependency points toward the small interface, not from the service to a concrete database library.

### Scheduler policy stays pure

`PlacementPolicy.decide()` accepts a job and worker snapshots, then returns a `PlacementDecision`. It does not write to the database. A pure function is easy to test because the same input always gives the same output.

### API schemas are boundary objects

Pydantic request models reject malformed external input. Response models deliberately choose which fields are public.

They are not the domain model. An API can evolve its JSON representation without giving up the internal state rules.

### Errors become stable HTTP responses at one boundary

Services raise meaningful application errors such as `JobNotFound` or `WorkerConflict`. `api/errors.py` translates them into status codes and stable error codes.

Keeping translation central prevents one route from returning `404` while another returns `500` for the same kind of failure.

### Migrations are append-only schema history

`backend/migrations/versions/` contains numbered database changes. An existing developer database may already have migrations `0001` and `0002`, so adding a table requires `0003` rather than rewriting history.

## M1–M4 map

| Milestone | Main idea | Read first |
| --- | --- | --- |
| M1 | API process starts safely | `main.py`, `api/health.py` |
| M2 | Jobs survive restart | `domain/job.py`, `services/jobs.py` |
| M3 | Workers safely lease and finish jobs | `domain/worker.py`, `services/workers.py` |
| M4 | Placement decisions are fair and explainable | `scheduler/policy.py` |
| M5 | Models execute through adapters with warm-model reuse | `domain/model.py`, `runtime/manager.py`, `services/workers.py` |
| M6 (current slice) | CLI stays thin and reuses the existing HTTP contracts | `cli/main.py`, `cli/client.py`, `tests/test_cli.py` |
| M6 (dashboard slice) | Browser overview remains a read-only API client | `dashboard/src/App.tsx`, `dashboard/src/api.ts`, `api/workers.py` |
| M6 (detail slice) | UI shows persisted evidence instead of recreating past decisions | `dashboard/src/App.tsx`, `api/jobs.py`, `services/workers.py` |

## How to read a test

An integration test usually follows Arrange–Act–Assert:

```text
Arrange: register workers and submit jobs
Act:     ask a worker for its next lease
Assert:  check the selected worker and saved explanation
```

Read the test function name first. Then identify these three sections. The test describes the system contract; implementation details may change while that contract remains stable.

## How to study one decision

For any non-trivial code path, answer:

1. What problem does this solve?
2. Which layer owns the rule?
3. What must always remain true?
4. What happens if two callers act concurrently?
5. What persists after restart?
6. What failure is returned to the caller?
7. What simpler or more complex alternative exists?

If an answer is missing, update this guide or the relevant feature document.

## How we will update this guide

Every milestone will add:

1. A short explanation of the new idea in this file.
2. A “read these files in this order” list.
3. Comments around the tricky code paths—not comments that merely repeat the code.
4. A plain-language API or demo document when the feature is visible to a user.

If you want personal scratch notes, create a local `notes/` directory and add it to your own global Git ignore file. The guide above should stay committed because it is part of making Conductor understandable as an open-source project.

## Questions to check your understanding

1. Why is SQL located in `storage/` rather than `services/`?
2. Why does the domain not import FastAPI?
3. Which code owns transaction boundaries?
4. How does the current CLI reuse job rules without duplicating them?
5. Which test would you read first to understand scheduler capacity?
