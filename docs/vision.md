# Product vision and V1 scope

## One-sentence definition

Conductor is a local-first control plane that queues AI inference jobs, selects an eligible local worker using explainable resource-aware scheduling, manages model residency, and exposes execution health through one API, CLI, and dashboard.

## Problem

Developers running local AI tools currently manage separate processes, APIs, model lifecycles, and resource limits. This creates avoidable cold starts, memory pressure, inconsistent observability, and manual recovery after failures.

Conductor provides one operational layer above heterogeneous runtimes. The runtimes perform inference; Conductor owns reliable execution and resource decisions.

## Primary user

A developer running multiple local AI workloads on one laptop who wants repeatable execution and visibility without operating a cluster.

## V1 success criteria

V1 is complete when a fresh contributor can run Conductor locally and demonstrate all of the following:

1. Submit the same job contract to two heterogeneous runtime adapters.
2. Observe a queued job being assigned using a documented, resource-aware score.
3. Prefer an eligible worker where the requested model is already resident.
4. Queue work when capacity is unavailable rather than oversubscribing memory.
5. Detect an expired worker lease and safely retry its unfinished job.
6. Load a model on demand and unload an idle model under a configured policy.
7. Cancel queued and running jobs with deterministic terminal state.
8. Inspect workers, models, queue depth, latency, failures, and scheduling rationale through the dashboard.
9. Perform the core submit, inspect, cancel, and benchmark flows through the CLI.
10. Start the supported local topology with one documented command and pass the automated test suite.

## V1 capabilities

### Control plane

- Versioned REST API for jobs, workers, model definitions, model residency, and operational views.
- Durable job, attempt, worker-registration, and model-residency metadata in SQLite.
- Idempotent job submission and guarded state transitions.
- Bounded in-process scheduling loop; the database remains the recovery source of truth.

### Scheduling

- Hard eligibility filters for runtime capability, model compatibility, worker health, concurrency slots, and memory headroom.
- Deterministic weighted scoring that favors a resident model, lower utilization, shorter local queue, and higher job priority.
- Persisted scheduling rationale sufficient to explain why a worker was selected or why a job remained queued.
- Bounded retries with backoff for retryable infrastructure failures.

### Workers and runtimes

- Multiple local worker processes with registration, epoch-based identity, heartbeats, graceful drain, and lease expiry.
- A deterministic fixture runtime for tests and demonstrations of failure behavior.
- At least two real, heterogeneous local runtime adapters before V1 release: an Ollama-compatible text runtime and an ONNX Runtime workload.
- Explicit load, ready, idle, and unload behavior behind a common runtime contract.

### User experience

- CLI for submitting, listing, inspecting, cancelling, and benchmarking jobs.
- Read-only operational dashboard with live job, worker, model, and host-resource views.
- Structured logs and Prometheus-compatible metrics.
- Docker-based reproducible setup where supported, plus native development instructions for Apple Silicon.

## Explicit non-goals

V1 does not include:

- multi-host or cloud execution;
- Kubernetes, Kafka, Redis, or distributed consensus;
- GPU-aware scheduling across discrete accelerators;
- user accounts, authentication, billing, quotas, or multi-tenancy;
- workflow DAGs, agents, prompt management, RAG, or a chat interface;
- training, fine-tuning, model conversion, or a model marketplace;
- automatic model-quality recommendations;
- arbitrary untrusted code execution;
- predictive preloading based on learned behavior.

These exclusions protect the central claim: Conductor reliably manages heterogeneous local inference under constrained resources.

## Product principles

1. **Explain decisions.** Every scheduling outcome must be inspectable.
2. **Fail conservatively.** Unknown capacity or an expired lease makes a worker ineligible.
3. **Keep truth durable.** In-memory queues accelerate work but do not define recoverable state.
4. **Separate policy from mechanism.** Scheduling policy must not know HTTP, SQL, or runtime SDK details.
5. **Prove behavior.** Failure injection and deterministic runtimes are first-class test tools.
6. **Earn complexity.** A new dependency or process boundary requires a measured V1 need.

## Release boundary

The resume-ready release is `v1.0.0`. Later improvements are new product capabilities, not unfinished V1 work. Documentation and UI must describe only behavior that the release actually implements.
