# How Conductor chooses a worker

M4 makes every choice explainable. When a worker asks for work, Conductor looks at all registered workers and checks three simple rules:

1. Is the worker ready (not draining)?
2. Can it do this task type?
3. Does it have a free execution slot?

Among eligible workers, Conductor picks the least busy one. If two workers are equally busy, it picks the alphabetically first worker ID. This tie-break makes demos and tests predictable.

For every evaluation, Conductor saves a small decision record. You can read it at:

```text
GET /api/v1/jobs/{job_id}/scheduling-decisions
```

The response tells you which worker was selected and gives every candidate a reason such as `eligible`, `no_free_slots`, `task_not_supported`, or `worker_not_ready`.

This is intentionally a simple scheduler. M5 adds model-specific information such as whether a model is already loaded; M4 focuses on proving fair, inspectable capacity decisions first.
