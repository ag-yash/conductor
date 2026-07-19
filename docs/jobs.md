# Durable jobs: the M2 demo

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

## Prove that jobs survive restarts

1. Submit a job.
2. Stop Conductor with `Ctrl+C`.
3. Start `conductor-api` again.
4. Fetch the same job ID.

The job remains because SQLite—not process memory—is the source of truth.
