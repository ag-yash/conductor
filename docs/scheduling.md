# How Conductor chooses a worker

Conductor makes every choice explainable. When a worker asks for work, it checks these rules:

1. Is the worker ready (not draining)?
2. Can it do this task type?
3. Does it have a free execution slot?
4. When it has a resource report, does the model fit after Conductor's 512 MiB memory reserve?

Among eligible workers, Conductor first prefers a worker that already has the
requested model loaded. This avoids a cold model load. If several candidates are
equally warm (or all cold), it picks the least busy one, then the alphabetically
first worker ID. This makes demos and tests predictable.

## Eligibility before scoring

Conductor first asks, “Is this worker allowed to run the job?” Only then does it ask, “Which allowed worker is preferable?”

These are different:

- **Eligibility constraint:** a rule that cannot be overridden, such as task support.
- **Score/preference:** a way to rank workers that already passed every constraint.

No excellent score can make an ineligible worker eligible. For example, an empty worker that does not support `text.generate` cannot win a text-generation job.

## Concrete example

Assume the job needs `text.generate`:

| Worker | Status | Supported task | Slots | Result |
| --- | --- | --- | --- | --- |
| `worker-a` | ready | `text.generate` | 1/1 active | Rejected: `no_free_slots` |
| `worker-b` | ready | `text.generate` | 0/2 active | Eligible |
| `worker-c` | draining | `text.generate` | 0/2 active | Rejected: `worker_not_ready` |
| `worker-d` | ready | `image.detect` | 0/2 active | Rejected: `task_not_supported` |

`worker-b` is the only eligible worker, so it wins.

If both `worker-b` and `worker-e` have `0/2` active slots, the scheduler uses worker ID as a stable tie-breaker. It consistently chooses `worker-b`.

## Current M4 load calculation

M4 calculates a worker’s load ratio:

```text
load ratio = active slots / maximum parallel jobs
```

Examples:

```text
worker-a: 1 / 1 = 1.00 (full)
worker-b: 1 / 2 = 0.50
worker-c: 2 / 4 = 0.50
```

The smallest eligible ratio wins. When ratios are equal, worker ID breaks the tie.

This calculation is explainable and deterministic. Model residency is now a
first preference: a warm worker wins over a cold one only after both pass all
hard constraints. CPU, job priority, and queue depth remain future work.

### Warm-model example

`worker-a` and `worker-b` both have zero active slots. `worker-b` has already
loaded `qwen-demo`; `worker-a` has not. For a `qwen-demo` job, `worker-b` wins
with `resident_model_preferred`, even though `worker-a` comes first
alphabetically. The saved candidate data includes `model_is_resident` so the
dashboard can show this was a measured scheduling input, not a guess.

## Memory headroom when telemetry exists

Workers can now report actual host CPU and memory measurements. For a worker
with a current report, the scheduler treats memory as a hard safety constraint:

```text
safe memory headroom = host available memory - 512 MiB reserve
```

If a model's `expected_memory_bytes` is larger than that headroom, the worker is
rejected with `insufficient_memory_headroom`. The decision record includes both
the available memory and the required model memory, so the dashboard can explain
the result later.

This first rollout does not reject workers that have not reported telemetry yet;
that preserves compatibility with manually registered workers. The standalone
worker now reports telemetry automatically, but CPU is still collected for
visibility rather than worker ranking. See
[`resource-telemetry.md`](resource-telemetry.md) for a runnable example.

## Why stable tie-breaking matters

Without a tie-breaker, equal candidates might win in database-return order. That order can change across runs, making a test flaky and an operational decision difficult to reproduce.

Stable ordering gives:

```text
same job + same worker snapshot → same decision
```

This property is called determinism.

For every evaluation, Conductor saves a small decision record. You can read it at:

```text
GET /api/v1/jobs/{job_id}/scheduling-decisions
```

The response tells you which worker was selected and gives every candidate a reason such as `eligible`, `no_free_slots`, `task_not_supported`, or `worker_not_ready`.

Example response:

```json
[
  {
    "outcome": "assigned",
    "reason": "least_loaded_eligible_worker",
    "selected_worker_id": "worker-b",
    "candidates": [
      {
        "worker_id": "worker-a",
        "eligible": false,
        "reason": "no_free_slots",
        "active_slots": 1,
        "max_parallel_jobs": 1
      },
      {
        "worker_id": "worker-b",
        "eligible": true,
        "reason": "eligible",
        "active_slots": 0,
        "max_parallel_jobs": 2
      }
    ]
  }
]
```

## Why persist the explanation?

A log entry might be rotated or difficult to find. Current worker state also changes:

```text
10:00 worker-a was full, so worker-b won
10:01 worker-a completed a job and became free
```

If we inspected only current state at 10:01, the 10:00 decision might look wrong. The immutable scheduling record preserves the exact candidate snapshot used at decision time.

## Pure policy, impure service

`PlacementPolicy.decide()` is pure:

- it receives Python data;
- it performs no SQL or HTTP calls;
- it returns a decision;
- the same input produces the same output.

`WorkerService.next_lease()` performs effects:

- reads workers and attempts;
- calls the policy;
- inserts an attempt;
- updates the job;
- saves the decision;
- commits the transaction.

Separating these responsibilities makes scheduling logic easy to test and keeps database failures out of the ranking algorithm.

The policy now includes one model-specific preference: ready residency. It still
does not rank by CPU, priority, or queue depth until those inputs have a clear
measurement and test contract.

## Trade-offs in the current design

- Poll-based workers simplify connectivity but can add a small scheduling delay.
- Load ratio is easy to explain but does not measure memory pressure.
- Alphabetical tie-breaking is reproducible but does not provide long-term round-robin fairness.
- Storing every evaluation improves debugging but increases database rows.

These are conscious V1 trade-offs, not accidental limitations.

## Questions to check your understanding

1. Why are constraints evaluated before scores?
2. Why can a worker with zero active slots still be ineligible?
3. What problem does stable tie-breaking solve?
4. Why save a candidate snapshot instead of reading current state later?
5. Why does the pure policy not query SQLite itself?
