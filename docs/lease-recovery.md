# Recover work after a worker disappears

This feature protects a job when a worker process stops sending heartbeats.

For example, imagine a laptop runs a model and then its terminal is closed. The
control plane cannot know whether the process crashed, the laptop slept, or the
network temporarily failed. It therefore uses a careful rule:

> After 15 seconds without a heartbeat, Conductor no longer trusts that worker's lease.

It marks the worker **unreachable**. Any active attempt owned by that exact
process becomes **lost**. The job is then queued again if it has attempts left.

## The recovery timeline

```text
worker-a / process-1 leases job J1 as attempt A1
        ↓
worker stops heartbeating
        ↓
heartbeat deadline passes
        ↓
attempt A1 becomes lost; worker-a becomes unreachable
        ↓
job J1 returns to queued, if its retry budget remains
        ↓
worker-b leases J1 as a new attempt A2
```

The old process cannot later overwrite the retry. Its process-instance ID is
old, and A1 is no longer J1's active attempt.

## Retry budget

Every job has `max_attempts`. A job with `max_attempts: 3` can have attempts
A1, A2, and A3. If A3's worker lease expires too, Conductor marks the job
`failed` rather than retrying forever.

This prevents an unavailable model or broken machine from silently filling the
queue with the same work forever.

## How recovery runs

Recovery runs automatically whenever a worker polls for its next lease. This is
a useful local-first design: a healthy worker arriving to ask for work also
helps clean up work abandoned by another worker.

For a demo or operational check, run it explicitly:

```bash
conductor workers recover-expired-leases
```

The result reports four counts:

- `unreachable_workers`: workers whose heartbeat deadline passed;
- `lost_attempts`: in-progress attempts no longer trusted;
- `retried_jobs`: jobs returned to the queue; and
- `failed_jobs`: jobs with no retry budget left.

## Important limitation

This is a heartbeat-based safety mechanism, not a perfect crash detector. A
worker may be slow or temporarily disconnected. That is why Conductor rejects
late progress rather than allowing two processes to finish the same job.

## Code path to trace

1. `domain/worker.py` defines `unreachable`.
2. `services/workers.py` implements `recover_expired_leases`.
3. `storage/repositories.py` finds active attempts and calculates the next
   attempt ordinal.
4. `api/workers.py` exposes the recovery summary.
5. `tests/test_workers_api.py` proves both retry and exhausted-budget flows.
