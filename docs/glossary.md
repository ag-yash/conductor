# Conductor glossary

This glossary gives short definitions. Feature documents contain longer examples.

| Term | Plain-language meaning | Conductor example |
| --- | --- | --- |
| API | A defined way for one program to request work from another | A client submits a job with `POST /api/v1/jobs` |
| Aggregate | A group of related state protected by one set of rules | A `Job` controls its status and active attempt |
| Canonical request | One stable representation of input, independent of dictionary ordering | Used to determine whether two idempotent submissions are really the same |
| Control plane | The part that decides and coordinates; it does not perform the heavy inference itself | Conductor stores jobs and selects workers |
| Deterministic | The same input always produces the same output | Equal workers are consistently ordered by worker ID |
| Domain model | Python objects that express business rules without HTTP or database code | `Job`, `Worker`, and `ExecutionAttempt` |
| Durable | Still present after the process restarts | Jobs are stored in SQLite rather than only in memory |
| Heartbeat | A small repeated message meaning “this process is still alive” | A worker periodically updates `last_heartbeat_at` |
| Idempotency | Safely repeating a request without repeating its effect | Retrying the same job submission returns the original job |
| Immutable | Not changed in place after creation | Domain methods return a new version of a `Job` |
| Invariant | A rule that must always remain true | A job has at most one active attempt |
| Lease | Temporary permission to own or perform work | A worker receives an execution attempt for a job |
| Migration | A versioned database-structure change | Migration `0003` creates scheduling-decision storage |
| Model residency | A model being loaded and usable inside a worker process | Conductor stores a snapshot for `fixture-text` on `laptop-worker/process-1` |
| Cold start | Extra work needed before a model can serve its first request | Loading model weights before the first invocation |
| Warmup | An intentionally unmeasured execution that prepares a runtime before a benchmark | One fixture invocation before three timed samples |
| Benchmark summary | A durable record of repeated execution timing for one model/task/worker combination | Mean and min/max wall-clock time stored in SQLite |
| Modular monolith | One deployable application split into strongly separated code modules | Conductor’s API, services, scheduler, and storage live in one backend process |
| Optimistic concurrency | Detecting conflicting writes using a version check instead of locking everything early | Updating job version `3` succeeds only if the database still contains version `2` |
| Process-instance ID | Identity of one particular run of a logical worker | `demo-worker` may restart from `process-a` to `process-b` |
| Repository | Code that hides database queries behind domain-focused operations | `SqlJobRepository.get(job_id)` |
| Repository port | An interface describing what storage must do without choosing a database | `JobRepository` in `services/ports.py` |
| Runtime adapter | Code that translates Conductor’s common runtime contract into one AI runtime’s API | The fixture and Ollama adapters implement `load`, `invoke`, and `unload` |
| Scheduler | Code that decides where queued work should run | `PlacementPolicy` selects an eligible worker |
| Snapshot | A read-only picture of state at one point in time | Worker status and active slots used for one scheduling decision |
| State machine | A list of allowed states and legal movements between them | A job may move from `queued` to `assigned`, but not directly to `succeeded` |
| Terminal state | A final state that cannot change again | `succeeded`, `failed`, and `cancelled` |
| Unit of work | One transaction shared by several repositories | Creating an attempt and assigning its job commit together |
| Worker | A process that performs jobs selected by the control plane | A local process capable of `text.generate` |
