# V1 implementation roadmap

Each milestone ends in a runnable, reviewable state and adds only behavior needed by the V1 success criteria.

## M1 — Executable control-plane shell ✅

- FastAPI application factory and typed settings.
- Versioned health and readiness endpoints.
- Structured logging and request correlation.
- Unit tests and CI quality gates.

Demo: start the control plane and inspect build/readiness information.

## M2 — Durable job core ✅

- Job and attempt domain objects with guarded transitions.
- SQLite migrations, repository ports, and implementations.
- Idempotent submission, inspection, listing, and queued cancellation.

Demo: submit duplicate-safe jobs and restart without losing them.

## M3 — Worker leases and deterministic execution

- Worker registration, epochs, heartbeat leases, drain behavior, and polling.
- Deterministic fixture runtime and local worker process.
- Attempt leasing, progress, results, and late-message rejection.

Demo: execute jobs, terminate a worker, and observe safe recovery.

## M4 — Explainable resource-aware scheduling

- Eligibility constraints and immutable scheduling snapshots.
- Deterministic scoring, stable tie-breaking, capacity reservation, and deferral reasons.
- Retry decisions and bounded backoff.

Demo: show why one worker wins and why an unschedulable job waits.

## M5 — Heterogeneous AI runtimes and model lifecycle

- Ollama-compatible text adapter and one ONNX Runtime workload.
- Model definition and residency lifecycle.
- Idle eviction and memory-pressure policy.
- Benchmark command and recorded latency/resource summaries.

Demo: run two AI task kinds through one API and show warm-model preference and unload behavior.

## M6 — Operator experience

- CLI for submit, inspect, list, cancel, and benchmark flows.
- Dashboard for jobs, workers, queue, models, resources, and scheduling rationale.
- Live updates using a minimal justified transport.

Demo: operate and explain the system without reading terminal logs.

## M7 — Release hardening

- Prometheus-compatible metrics, failure-injection scenarios, and integration tests.
- Docker setup, native Apple Silicon setup, CI, security review, and contributor documentation.
- Reproducible demo script, screenshots/video, performance baseline, and `v1.0.0` release notes.

Demo: clone-to-demo walkthrough on a clean machine.

## Scope gate

A feature not required by [`vision.md`](vision.md) waits until after `v1.0.0`. In particular, no V1 milestone introduces multi-host scheduling, workflow DAGs, authentication, Kubernetes, Kafka, or predictive model selection.
