# Domain model

## What a domain model is

A database row answers, “What data is stored?” An API schema answers, “What JSON may enter or leave?” A domain object answers, “What rules must always be true?”

For example, a database column can physically store any status string. The `Job` domain object restricts status changes:

```text
queued → assigned → running → succeeded   valid
queued → succeeded                         invalid
```

That rule belongs in the domain because it must be enforced whether the action comes from HTTP, a CLI, a recovery loop, or a future dashboard.

The sections below describe the intended V1 model. Some M5–M7 fields are planned but not implemented yet; the roadmap introduces them only when their behavior is testable.

## Three representations of one idea

A job appears in three forms:

| Form | Location | Purpose |
| --- | --- | --- |
| Domain object | `domain/job.py` | Enforces job rules |
| Database record | `models/records.py` | Defines stored columns |
| API response | `api/jobs.py` | Defines public JSON |

We translate between them deliberately. If we reused one SQLModel class everywhere, database choices could leak into scheduling rules and private columns could accidentally appear in API responses.

## Modeling rules

- Domain identifiers are opaque and immutable.
- Timestamps are timezone-aware UTC values.
- Mutable aggregates carry a monotonically increasing version.
- State changes occur through named domain operations, never direct field mutation.
- API schemas and database rows translate to domain objects; they are not domain objects.
- “Busy” and “idle” are derived capacity conditions, not worker or model lifecycle states.

### Plain-language examples

- **Opaque identifier:** code treats a job ID as an identity, not as a value from which business meaning should be parsed.
- **UTC timestamp:** `12:00 UTC` means the same instant on every machine, unlike an unqualified local time.
- **Monotonic version:** the version moves `0 → 1 → 2`; it never moves backward.
- **Named transition:** call `job.assign(attempt_id)` instead of writing `job.status = "assigned"`.
- **Derived condition:** a worker is busy because all slots are occupied, not because someone manually set a separate `busy` flag that could become inconsistent.

## Aggregates and entities

### Job

Represents the user's durable intent to perform one inference operation.

Think of a job as an order:

```text
task:       text.generate
model_id:   qwen-demo
input:      {"prompt": "Explain leases"}
priority:   normal
status:     queued
```

The order survives worker failures. A worker may make several execution attempts, but the original user intent remains one job.

| Field | Meaning |
| --- | --- |
| `id` | Opaque job identity |
| `idempotency_key` | Client-scoped duplicate-submission guard |
| `task` | Runtime-neutral task kind and version |
| `model_id` | Requested model definition |
| `input_ref` | Validated reference to input data or an inline bounded payload |
| `parameters` | Canonical, bounded inference parameters |
| `priority` | V1 priority class used by queue ordering |
| `status` | Current job lifecycle state |
| `retry_policy` | Maximum attempts and backoff parameters within V1 limits |
| `active_attempt_id` | Current attempt, if any |
| `result_ref` | Output reference or bounded inline result after success |
| `failure` | Stable failure category and safe message after terminal failure |
| `created_at`, `updated_at` | Audit timestamps |
| `version` | Optimistic concurrency token |

Invariants:

- A job has at most one active attempt.
- A terminal job has no active attempt.
- A succeeded job has result metadata and no terminal failure.
- A failed job has a terminal failure and exhausted or disallowed retries.
- Idempotency identity and canonical request content never change.

An **invariant** is a rule that must be true before and after every operation. “A job has at most one active attempt” prevents two workers from both being accepted as the current owner.

Why separate `Job` from `ExecutionAttempt`? If we stored only one mutable execution record, a retry would erase evidence of the earlier failure. Separate attempts preserve history.

### ExecutionAttempt

Represents one placement and execution of a job. Retries create new attempts rather than resetting history.

Example:

```text
Job J1
├── Attempt A1 → worker-a/process-1 → lost
└── Attempt A2 → worker-b/process-4 → succeeded
```

`J1` represents what was requested. `A1` and `A2` represent what the system tried.

| Field | Meaning |
| --- | --- |
| `id` | Opaque attempt identity |
| `job_id`, `ordinal` | Parent job and one-based attempt number |
| `worker_id`, `worker_instance_id` | Assigned logical worker and exact process |
| `status` | Attempt lifecycle state |
| `lease_expires_at` | Deadline after which ownership may be declared lost |
| `started_at`, `finished_at` | Execution timing |
| `failure` | Retryable or terminal categorized failure |
| `resource_summary` | Bounded execution resource measurements |
| `version` | Optimistic concurrency token |

Invariants:

- `(job_id, ordinal)` is unique.
- Worker identity and process-instance ID cannot change after assignment.
- Only the assigned current process instance may renew or report the attempt.
- An attempt has exactly one terminal outcome.

The exact process identity matters. If `worker-a` restarts, the new process must not inherit permission to report results for work leased to the old process.

### WorkerRegistration

Represents one logical worker and its current process incarnation.

The logical ID is like an employee name; the process-instance ID is like today’s security badge:

```text
worker ID:           transcript-worker
worker_instance_id:  process-2026-07-28-a
```

After a restart, the worker ID stays stable but the process-instance ID changes.

| Field | Meaning |
| --- | --- |
| `id` | Stable configured worker identity |
| `worker_instance_id` | New opaque process identity on every restart |
| `status` | Registration lifecycle state |
| `capabilities` | Supported runtime kinds, tasks, and concurrency limits |
| `resource_capacity` | Declared schedulable CPU, memory, and slots |
| `resource_snapshot` | Latest measured use and timestamp |
| `lease_expires_at` | Current registration lease deadline |
| `active_attempt_ids` | Reserved or executing attempts |
| `registered_at`, `last_heartbeat_at` | Audit timestamps |
| `version` | Optimistic concurrency token |

Invariants:

- Only the current process instance can heartbeat, poll, drain, or report work.
- Available capacity never exceeds declared capacity.
- An unreachable or draining worker receives no new assignments.
- Heartbeats update observations but cannot directly decide job outcomes.

### ModelDefinition

Represents trusted configuration for a model that Conductor is allowed to execute.

A model definition is metadata, not the model loaded in memory. It is comparable to an application configuration:

```text
id: qwen-small
runtime_kind: ollama
artifact: qwen2.5:1.5b
supported_tasks: [text.generate]
expected_memory: 2 GB
```

This object is implemented in `domain/model.py` and persisted through model
definition and residency repositories.

| Field | Meaning |
| --- | --- |
| `id` | Stable model identity |
| `display_name` | Human-readable name |
| `runtime_kind` | Adapter contract required to run the model |
| `artifact` | Trusted runtime-specific artifact descriptor |
| `supported_tasks` | Task contracts the model accepts |
| `resource_profile` | Conservative expected memory and CPU requirements |
| `load_policy` | Idle timeout and unload eligibility |
| `enabled` | Whether new jobs may request the model |
| `revision` | Immutable configuration revision |

Model definitions are versioned configuration, not downloaded model binaries.

### ModelResidency

Represents the lifecycle of one model definition on one worker process instance.

Residency answers a runtime question: “Is this model currently loaded inside this exact worker process?”

```text
Model definition: qwen-small exists in configuration
Model residency:  qwen-small is READY in worker-a/process-3
```

A process restart destroys actual memory, so residency from the old process must never be considered ready.

| Field | Meaning |
| --- | --- |
| `id` | Opaque residency identity |
| `model_id`, `model_revision` | Exact requested definition |
| `worker_id`, `worker_instance_id` | Hosting logical worker and exact process |
| `status` | Load lifecycle state |
| `loaded_at`, `last_used_at` | Lifecycle timestamps |
| `active_execution_count` | Current consumers |
| `measured_memory_bytes` | Latest observed footprint, if available |
| `failure` | Safe categorized load or runtime failure |
| `version` | Optimistic concurrency token |

Invariants:

- At most one active residency exists for a model revision on a worker process instance.
- A residency with active executions cannot begin unloading.
- Residency from a prior worker process instance is never considered ready.
- `READY` describes availability; idle is derived when active count is zero.

### SchedulingDecision

An immutable audit record produced for an assignment or deferral.

It contains the job and policy version, snapshot timestamp, candidate constraint outcomes, normalized score factors, selected worker if any, and stable reason codes. It supports debugging and offline policy benchmarks but does not replace job state.

Example:

```text
Job: J2
Outcome: assigned
Selected: worker-b

worker-a → rejected: no_free_slots
worker-b → eligible: 0 of 2 slots active
```

The record is immutable because it describes a past decision. A later heartbeat must not rewrite history.

## Value objects

### TaskSpec

A versioned task name plus a bounded, validated input and parameter contract. Runtime adapters declare which task versions they support.

### ResourceCapacity and ResourceSnapshot

Capacity describes schedulable limits. A snapshot describes measured usage with a timestamp. Scheduler input rejects stale snapshots and uses bytes or normalized integer units internally rather than ambiguous display units.

Capacity is the maximum; a snapshot is the latest observation:

```text
capacity:  4 execution slots
snapshot:  3 slots currently active
available: 1 slot (derived)
```

### WorkerCapabilities

An immutable declaration of runtime kinds, supported task versions, maximum parallel executions, and optional runtime-specific features. Capabilities are replaced atomically when a new worker process instance registers.

### Failure

A stable category, retryability flag, safe public message, and internal correlation identifier. Tracebacks and secrets remain in protected logs, not domain responses.

The category drives behavior. `WORKER_LOST` can be retried; `INVALID_REQUEST` should not be retried because repeating invalid input will not fix it.

### RetryPolicy

Maximum attempts, initial backoff, multiplier, and bounded maximum backoff. V1 allows only system-configured safe limits; users cannot request unbounded retries.

### SchedulingFactors

Normalized values and weights used to calculate a placement score, including model residency, memory headroom, CPU utilization, available slots, and local queue pressure.

## Domain services

### PlacementPolicy

A pure policy that accepts a job, model definition, eligible snapshot set, and policy configuration. It returns a placement or a structured deferral without performing I/O.

### RetryDecisionPolicy

Determines whether a failed or lost attempt creates a delayed retry, considering failure category, cancellation, attempt count, and retry policy.

### ModelEvictionPolicy

Ranks unload-eligible idle residencies under timeout or memory pressure. It cannot evict a residency with active executions.

## Repository ports

Application services depend on ports for jobs, attempts, workers, model definitions, residencies, scheduling decisions, and unit-of-work transactions. Concrete SQLite repositories belong to `storage` and must enforce database uniqueness and compare-and-set constraints that mirror domain invariants.

In simpler terms:

```text
Service asks: “Give me job J1”
        ↓
JobRepository interface
        ↓
SQLite implementation runs the query
```

The service knows what it needs but does not know SQL. The cost is additional mapping code. We accept that cost because it keeps correctness rules independent from database tooling and makes pure unit tests possible.

## Deliberate omissions

There is no `User`, `Cluster`, `Node`, `Workflow`, `Prompt`, `Conversation`, or `Agent` aggregate in V1. A local worker is modeled directly; introducing cloud-oriented nouns would misrepresent the product boundary.

## Questions to check your understanding

1. Why are `JobRecord` and `Job` separate classes?
2. Why does a retry create a new attempt?
3. What invariant prevents two current attempts for one job?
4. Why does a worker restart need a new process-instance ID?
5. Why is model definition different from model residency?
