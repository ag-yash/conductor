# Workers in simple terms

A **worker** is a small process that does jobs. The control plane stores jobs; a worker asks whether there is work it can do.

For example, imagine two terminals:

1. Terminal A runs Conductor's API.
2. Terminal B acts as `demo-worker` and says, “I can do `text.generate` jobs.”

The worker first registers. It then sends a heartbeat every so often. A heartbeat is simply a short “I am still alive” message.

## Control plane versus worker

| Control plane | Worker |
| --- | --- |
| Accepts and stores jobs | Performs the actual work |
| Chooses an eligible worker | Declares what task types it supports |
| Protects job state | Loads a model and invokes a runtime |
| Records decisions | Reports start, completion, or failure |

Keeping them separate prevents a slow model call from blocking the API process.

## Registration

A worker introduces itself with:

```json
{
  "worker_id": "demo-worker",
  "worker_instance_id": "process-a",
  "supported_tasks": ["text.generate"],
  "max_parallel_jobs": 1
}
```

- `worker_id` is the stable logical name.
- `worker_instance_id` identifies this exact running process.
- `supported_tasks` tells the scheduler what the worker understands.
- `max_parallel_jobs` is the maximum number of execution slots.

The control plane stores this registration durably. A worker that never registered cannot poll or report an attempt.

## Why `worker_instance_id` exists

The worker name (`demo-worker`) stays the same across restarts, but the process does not. When Terminal B is restarted, it supplies a new `worker_instance_id`, such as `process-b`.

This lets Conductor reject a late message from `process-a`. In plain English: an old, already-restarted worker is not allowed to finish a job by mistake.

### Restart timeline

```text
10:00 demo-worker/process-a registers
10:01 process-a receives attempt A1
10:02 process-a becomes disconnected
10:03 demo-worker/process-b registers after restart
10:04 an old message from process-a arrives
10:04 Conductor rejects it because process-b is current
```

Some distributed-systems material calls this changing identity an **epoch** or **incarnation**. Conductor uses `worker_instance_id` because it describes the idea more directly.

## Heartbeats

A heartbeat updates the last time Conductor heard from the current process:

```text
POST /api/v1/workers/demo-worker/heartbeat
Worker-Instance-ID: process-a
```

A heartbeat does not mean a job succeeded. It only says the worker process is alive enough to communicate.

The current implementation protects against stale process instances. Future
lease-expiry logic will additionally use missing heartbeats conservatively. “No
heartbeat” means “do not trust this worker for new work,” not “we have proof that
the process is dead.”

## M3 request flow

```text
register → heartbeat → ask for a lease → start attempt → complete attempt
```

When the worker asks for a lease, Conductor creates an execution attempt and changes the job from `queued` to `assigned` together. That prevents two workers from owning the same job.

### What “together” means

The attempt insert and job update use one database transaction:

```text
BEGIN
  create attempt A1
  change job J1 from queued to assigned
  record scheduling decision
COMMIT
```

If one write fails, the transaction rolls back all of them. We never want a job pointing to an attempt that does not exist or an attempt claiming a job that still looks queued.

## Polling for a lease

Workers ask for work:

```text
POST /api/v1/workers/demo-worker/leases/next
Worker-Instance-ID: process-a
```

Possible responses:

- `200` with a job and attempt means this worker owns the new lease;
- `204 No Content` means there is no suitable work for this worker now;
- `409 Conflict` means the process identity or current state is stale.

`204` is normal. A worker may poll again later.

## Draining

Draining means “finish current work, but accept nothing new.” It is used before a graceful shutdown or maintenance:

```text
READY → DRAINING
```

A draining worker may still report its current attempt. The scheduler simply excludes it from new placements.

## Scope of this milestone

M3 deliberately uses a predictable success path. It proves the worker/control-plane protocol before we attach an actual AI model runtime in M5. M4 adds smarter worker selection, retry policy, and capacity accounting.

M4 now adds task, readiness, and slot-aware placement. Lease expiry, automatic retry, and real runtime calls remain later work.

## Follow leasing through the code

1. `api/workers.py` validates worker headers and payloads.
2. `services/workers.py` checks the current process instance and coordinates leasing.
3. `scheduler/policy.py` explains which worker should win.
4. `storage/unit_of_work.py` gives the operation one transaction.
5. `storage/repositories.py` persists workers, attempts, jobs, and explanations.
6. `tests/test_workers_api.py` proves restart and drain behavior.
7. `tests/test_scheduling_api.py` proves capacity-aware placement.

## Questions to check your understanding

1. Why do workers initiate polling?
2. What is the difference between `worker_id` and `worker_instance_id`?
3. Why does a heartbeat not update job status?
4. Why must attempt creation and job assignment be atomic?
5. Why can a ready worker still receive no work?
