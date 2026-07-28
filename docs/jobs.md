# Durable jobs: the M2 demo

## The main idea

Submitting a job is not the same as immediately running a Python function.

```text
HTTP request → validate → create durable job → return job ID
                                      ↓
                              worker runs it later
```

The client receives a stable identity even if no worker is currently available. This decouples accepting work from executing work.

## What M2 adds

M1 proved that the Conductor process could start reliably. M2 lets that process accept and remember work.

Conductor does not execute AI work yet. A submitted job stays `queued` until M3 introduces worker processes. This is deliberate: we first prove that job state is safe before allowing concurrent processes to change it.

## Start Conductor

```bash
source .venv/bin/activate
conductor-api
```

Interactive API documentation is available at `http://127.0.0.1:8080/docs`.

## Submit a job

```bash
curl -i http://127.0.0.1:8080/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: my-first-job' \
  -d '{
    "task": "text.generate",
    "model_id": "qwen-demo",
    "input": {"prompt": "Explain distributed systems simply."},
    "parameters": {"temperature": 0.2},
    "priority": "normal",
    "max_attempts": 3
  }'
```

The first submission returns HTTP `201 Created` and a durable job:

```json
{
  "id": "generated-job-id",
  "task": "text.generate",
  "model_id": "qwen-demo",
  "status": "queued",
  "version": 0
}
```

The real response includes the input, parameters, timestamps, and retry limit as well.

## What is an idempotency key?

Imagine clicking a payment button, losing your internet connection, and clicking again. The server must not charge you twice.

`Idempotency-Key` is the request's receipt number. If you repeat the exact same submission using `my-first-job`, Conductor returns the original job with HTTP `200 OK`. It does not create another job.

```text
Same key + same request      → return the original job
Same key + different request → reject with HTTP 409
New key + any valid request  → create a new job
```

This matters when clients retry after timeouts and do not know whether the first request succeeded.

### How Conductor decides whether the request is identical

JSON objects do not require a fixed key order. These two objects mean the same thing:

```json
{"prompt": "hello", "temperature": 0.2}
{"temperature": 0.2, "prompt": "hello"}
```

Conductor builds a **canonical representation**: it sorts keys and uses consistent JSON formatting. It hashes that stable byte sequence with SHA-256.

```text
canonical request → SHA-256 → request_hash
```

When an idempotency key is reused:

- matching hash means the same request, so return the original job;
- different hash means different work is trying to reuse the receipt number, so return `409 Conflict`.

The hash is not used as authentication. It is only a stable comparison value.

## Inspect and list jobs

Fetch one job:

```bash
curl http://127.0.0.1:8080/api/v1/jobs/generated-job-id
```

List queued jobs:

```bash
curl 'http://127.0.0.1:8080/api/v1/jobs?status=queued&limit=50&offset=0'
```

The list is bounded so one request cannot accidentally load an unlimited number of jobs into memory.

`limit` says how many rows to return. `offset` says how many matching rows to skip:

```text
offset=0, limit=50   → first page
offset=50, limit=50  → second page
```

Offset pagination is simple and sufficient for V1. For a very large, rapidly changing dataset, cursor pagination would give more stable performance, but it would add unnecessary complexity now.

## Cancel a queued job

```bash
curl -X POST http://127.0.0.1:8080/api/v1/jobs/generated-job-id/cancel
```

The status becomes `cancelled`, and the version changes from `0` to `1`.

The version is an edit counter:

```text
version 0 → original queued job
version 1 → job after cancellation
```

Later, if two concurrent operations both try to modify version `0`, only the first may succeed. The second sees that the version already changed instead of silently overwriting newer state. The technical term is **optimistic concurrency control**.

### Why “optimistic”?

We optimistically assume conflicts are uncommon, so readers do not lock the row before doing work. At update time, the SQL statement includes the expected old version:

```sql
UPDATE jobs
SET status = 'cancelled', version = 1
WHERE id = 'J1' AND version = 0;
```

If another operation already changed the version, this statement updates zero rows. Conductor detects that and returns a conflict instead of overwriting the newer state.

## What is an execution attempt?

A job describes what the user wants. An execution attempt describes one try to perform it.

```text
Job: "Generate this text"
  ├── Attempt 1: worker crashed
  └── Attempt 2: succeeded
```

Retries create new attempts instead of deleting previous history. M2 defines and tests the attempt state rules; M3 will create attempts when workers begin accepting jobs.

## What is a database migration?

The SQLite file holds persistent data. As Conductor evolves, its tables will need new columns or indexes.

A migration is a numbered instruction for safely changing an existing database structure. On startup, Conductor applies any missing migration before declaring itself ready. M2 begins with migration `0001`, which creates the `jobs` and `attempts` tables.

Migration files are ordered history:

```text
0001 create jobs and attempts
0002 create workers
0003 create scheduling decisions
```

We do not edit an old migration after it has been used. A new schema change gets a new migration so an existing checkout can move forward predictably.

## Prove that jobs survive restarts

1. Submit a job.
2. Stop Conductor with `Ctrl+C`.
3. Start `conductor-api` again.
4. Fetch the same job ID.

The job remains because SQLite—not process memory—is the source of truth.

## Follow one submission through the code

Read these files in order:

1. `api/jobs.py` validates the JSON and `Idempotency-Key` header.
2. `services/jobs.py` creates a canonical request, checks duplicates, and coordinates the transaction.
3. `domain/job.py` creates a valid queued `Job`.
4. `services/ports.py` defines the storage operations the service needs.
5. `storage/repositories.py` translates the `Job` into a `JobRecord`.
6. `models/records.py` defines the SQLite columns.
7. `tests/test_jobs_api.py` exercises the complete path.

### Why the route does not call SQLite directly

If the FastAPI route contained SQL and idempotency logic, that logic would be hard to reuse and hard to test without HTTP. Keeping it in `JobService` lets a future CLI use the same behavior.

## Common failure examples

| Situation | Result | Why |
| --- | --- | --- |
| Missing idempotency key | Validation error | Every submission needs retry protection |
| Same key, same request | Original job returned | Safe retry |
| Same key, different request | `409 Conflict` | Prevent accidental key reuse |
| Payload above configured limit | `413` | Protect memory and SQLite from unbounded input |
| Cancel missing job | `404` | Requested identity does not exist |
| Cancel non-cancellable job | `409` | State machine rejects the transition |

## Questions to check your understanding

1. Why do we return a job ID before inference runs?
2. Why is canonical JSON needed before hashing?
3. What exact bug does an idempotency key prevent?
4. Why does an optimistic update include the previous version?
5. Why are attempts separate from jobs?
