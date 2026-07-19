# State machines

These transitions are normative for V1. Implementations must reject transitions not listed here and must persist transitions using optimistic concurrency guards.

## Job lifecycle

```mermaid
stateDiagram-v2
    [*] --> QUEUED: accepted
    QUEUED --> ASSIGNED: attempt reserved
    ASSIGNED --> RUNNING: worker starts attempt
    ASSIGNED --> QUEUED: retry after rejection or loss
    RUNNING --> QUEUED: retry after retryable failure or loss
    QUEUED --> CANCELLED: cancel before assignment
    ASSIGNED --> CANCELLING: cancel requested
    RUNNING --> CANCELLING: cancel requested
    CANCELLING --> CANCELLED: worker confirms or lease expires
    ASSIGNED --> FAILED: non-retryable or exhausted
    RUNNING --> FAILED: non-retryable or exhausted
    CANCELLING --> FAILED: cancellation cannot hide committed terminal failure
    RUNNING --> SUCCEEDED: result committed
    QUEUED --> FAILED: scheduling deadline or invalidated model
    SUCCEEDED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

Rules:

- `QUEUED` is the only schedulable state.
- Assignment and attempt creation are one transaction.
- A retry closes the previous attempt before returning the job to `QUEUED`.
- `CANCELLING` stops new retries and records intent while cooperative cancellation completes.
- A running success racing with cancellation may commit only through a version guard. If success commits first, cancellation observes a terminal job; once `CANCELLING` commits first, a later success is rejected.
- `SUCCEEDED`, `FAILED`, and `CANCELLED` are immutable.

## Execution-attempt lifecycle

```mermaid
stateDiagram-v2
    [*] --> ASSIGNED: scheduler creates attempt
    ASSIGNED --> STARTING: worker accepts lease
    STARTING --> RUNNING: runtime invocation begins
    ASSIGNED --> LOST: lease expires
    STARTING --> LOST: lease expires
    RUNNING --> LOST: lease expires
    ASSIGNED --> CANCELLING: job cancellation
    STARTING --> CANCELLING: job cancellation
    RUNNING --> CANCELLING: job cancellation
    CANCELLING --> CANCELLED: execution stopped
    CANCELLING --> LOST: lease expires
    STARTING --> FAILED: load or startup failure
    RUNNING --> FAILED: execution failure
    RUNNING --> SUCCEEDED: result accepted
    SUCCEEDED --> [*]
    FAILED --> [*]
    LOST --> [*]
    CANCELLED --> [*]
```

Rules:

- Attempt status is historical; a retry always receives a new attempt identity.
- `LOST` means exclusive ownership expired, not that the worker definitely stopped.
- Reports from terminal or superseded attempts are acknowledged as stale and cannot mutate their job.
- Result persistence and transition to `SUCCEEDED` occur atomically from the control plane's perspective.

## Worker-registration lifecycle

```mermaid
stateDiagram-v2
    [*] --> REGISTERING: registration requested
    REGISTERING --> READY: accepted with lease
    READY --> DRAINING: graceful stop requested
    READY --> UNREACHABLE: registration lease expires
    DRAINING --> UNREACHABLE: registration lease expires
    UNREACHABLE --> READY: current epoch renews within recovery window
    UNREACHABLE --> REMOVED: recovery window expires
    DRAINING --> REMOVED: active attempts reach zero
    REGISTERING --> REMOVED: registration rejected
    REMOVED --> [*]
```

Rules:

- A process restart registers a new epoch; it does not revive its old attempt leases.
- `READY` means eligible for evaluation, not guaranteed schedulable capacity.
- `DRAINING` and `UNREACHABLE` workers receive no new work.
- Busy and idle are derived from reserved slots, not lifecycle states.
- Late heartbeats from a non-current epoch are rejected.

## Model-residency lifecycle

```mermaid
stateDiagram-v2
    [*] --> ABSENT
    ABSENT --> LOADING: load requested
    LOADING --> READY: adapter confirms load
    LOADING --> FAILED: load fails or times out
    READY --> UNLOADING: eviction selected
    READY --> FAILED: adapter reports unusable model
    UNLOADING --> ABSENT: adapter confirms release
    UNLOADING --> FAILED: unload fails or times out
    FAILED --> LOADING: bounded recovery
    FAILED --> ABSENT: discard failed residency
```

Rules:

- `ABSENT` is a conceptual state; persisted residency may be deleted after audit retention.
- Model use is permitted only in `READY` on the current worker epoch.
- A residency with an active execution count greater than zero cannot enter `UNLOADING`.
- Busy and idle are derived from active execution count and last-used time.
- Worker epoch loss invalidates all of that epoch's residencies regardless of their last reported state.

## Scheduling decision lifecycle

Scheduling decisions are immutable facts rather than mutable state machines. Each scheduling evaluation records either assignment or deferral. A later evaluation produces a new decision record using a new snapshot and policy version.

## Failure categories

V1 uses stable categories so retry behavior is deterministic:

| Category | Default retry | Example |
| --- | --- | --- |
| `INVALID_REQUEST` | No | Unsupported task parameters |
| `MODEL_UNAVAILABLE` | Conditional | Disabled or missing definition |
| `INSUFFICIENT_CAPACITY` | Defer, not attempt failure | No eligible memory headroom |
| `WORKER_LOST` | Yes | Execution lease expired |
| `MODEL_LOAD_FAILED` | Bounded | Runtime load error |
| `EXECUTION_TIMEOUT` | Bounded | Adapter deadline exceeded |
| `RUNTIME_ERROR` | Bounded | Transient inference failure |
| `RESULT_REJECTED` | No | Invalid or oversized result |
| `CANCELLED_BY_USER` | No | Explicit cancellation |
| `INTERNAL_ERROR` | Bounded and alerted | Unexpected control-plane failure |

Retryability stored on an individual failure is decided from the category plus current policy; it is not trusted from worker-provided input.
