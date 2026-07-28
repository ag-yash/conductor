# Workers in simple terms

A **worker** is a small process that does jobs. The control plane stores jobs; a worker asks whether there is work it can do.

For example, imagine two terminals:

1. Terminal A runs Conductor's API.
2. Terminal B acts as `demo-worker` and says, “I can do `text.generate` jobs.”

The worker first registers. It then sends a heartbeat every so often. A heartbeat is simply a short “I am still alive” message.

## Why `worker_instance_id` exists

The worker name (`demo-worker`) stays the same across restarts, but the process does not. When Terminal B is restarted, it supplies a new `worker_instance_id`, such as `process-b`.

This lets Conductor reject a late message from `process-a`. In plain English: an old, already-restarted worker is not allowed to finish a job by mistake.

## M3 request flow

```text
register → heartbeat → ask for a lease → start attempt → complete attempt
```

When the worker asks for a lease, Conductor creates an execution attempt and changes the job from `queued` to `assigned` together. That prevents two workers from owning the same job.

## Scope of this milestone

M3 deliberately uses a predictable success path. It proves the worker/control-plane protocol before we attach an actual AI model runtime in M5. M4 adds smarter worker selection, retry policy, and capacity accounting.
