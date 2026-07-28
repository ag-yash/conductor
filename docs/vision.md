# Product vision and V1 scope

## One-sentence definition

Conductor is a local-first control plane that queues AI inference jobs, selects an eligible local worker using explainable resource-aware scheduling, manages model residency, and exposes execution health through one API, CLI, and dashboard.

## The same definition in simpler words

A developer may run several AI tools locally. Each tool may use a different command, API, model format, and amount of memory.

Conductor provides one coordinator:

```text
Developer sends one job
          ↓
Conductor remembers it
          ↓
Conductor chooses a suitable local worker
          ↓
Worker runs the requested AI model
          ↓
Conductor records the result and operational history
```

“Local-first” means the useful V1 system runs on one developer machine without requiring a cloud account or hardware purchase.

## Problem

Developers running local AI tools currently manage separate processes, APIs, model lifecycles, and resource limits. This creates avoidable cold starts, memory pressure, inconsistent observability, and manual recovery after failures.

Conductor provides one operational layer above heterogeneous runtimes. The runtimes perform inference; Conductor owns reliable execution and resource decisions.

### Example problem

Without Conductor, a developer might manually run:

```bash
ollama serve
python whisper_server.py
python embedding_server.py
```

The developer must remember ports, check which processes are healthy, avoid loading too many models, and retry work after crashes.

With Conductor, those runtime differences eventually sit behind one job contract. Conductor does not replace Ollama or ONNX Runtime; it coordinates them.

## Primary user

A developer running multiple local AI workloads on one laptop who wants repeatable execution and visibility without operating a cluster.

The V1 user is intentionally single-machine and single-user. This lets us study scheduling, durability, failure recovery, process coordination, and model lifecycle without adding authentication or multi-host networking first.

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

- Multiple local worker processes with registration, process-instance identity, heartbeats, graceful drain, and lease expiry.
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

### What these principles prevent

| Principle | Prevents |
| --- | --- |
| Explain decisions | “The scheduler chose it somehow” behavior |
| Fail conservatively | Assigning work using stale or unknown capacity |
| Keep truth durable | Losing queued work when the process restarts |
| Separate policy from mechanism | Scheduling rules coupled to FastAPI or SQL |
| Prove behavior | Failure recovery that exists only in a diagram |
| Earn complexity | Adding Kafka, Redis, or Kubernetes without a real need |

## Release boundary

The complete initial release is `v1.0.0`. Later improvements are new product capabilities, not unfinished V1 work. Documentation and UI must describe only behavior that the release actually implements.

## Why important alternatives are excluded

- **No Kubernetes:** local worker processes already let us study scheduling and failure handling. Kubernetes would add deployment complexity before it solves a V1 need.
- **No Kafka:** SQLite is the durable source of truth and current event volume is local-machine scale.
- **No arbitrary code execution:** accepting shell commands would create a much larger security boundary than trusted model adapters.
- **No workflow DAGs:** one durable inference job is enough to prove the execution platform before coordinating multi-step workflows.
- **No predictive scheduler:** deterministic heuristics are easier to explain, test, and benchmark first.

## Questions to check your understanding

1. What does Conductor coordinate that Ollama itself does not?
2. Why is local-first a useful constraint rather than merely a limitation?
3. Why does V1 use trusted runtime adapters instead of arbitrary scripts?
4. Why is explainability a product principle for the scheduler?
5. Name one excluded technology and the evidence we would need before adding it.
