# Conductor

Conductor is an intelligent, local-first AI workload manager for developers. It will provide a unified way to schedule, run, and observe heterogeneous AI workloads while managing limited local compute and memory responsibly.

Conductor currently provides a production-oriented control-plane shell plus a durable job API. Jobs are stored in SQLite, duplicate submissions are handled safely, state changes are guarded, and queued work can be inspected or cancelled. Job scheduling and AI execution are introduced in later milestones.

## Product principles

- **Local-first:** useful on a developer laptop without cloud infrastructure.
- **Runtime-agnostic:** the control plane will not be coupled to one model provider.
- **Resource-aware:** scheduling and model lifecycle decisions will account for local constraints.
- **Observable:** jobs, workers, models, and resource use will be explainable.
- **Focused:** Conductor is AI infrastructure, not a chatbot or RAG application.

## Architecture direction

Conductor begins as a modular monolith with independently testable modules and separate worker processes.

```text
CLI / Dashboard
       |
     API
       |
Conductor control plane
  |-- jobs and services
  |-- scheduler
  |-- worker management
  |-- runtime management
  |-- storage and metrics
       |
Local worker processes
```

The boundaries are intentionally documented before implementation. See [`docs/`](docs/) for design material as it is added.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `backend/` | Python control plane and its architectural modules |
| `dashboard/` | Browser-based operational dashboard |
| `shared/` | Explicit cross-component contracts and fixtures |
| `tests/` | Repository-level and cross-component verification |
| `docs/` | Product, architecture, decisions, and roadmap |
| `docker/` | Container-specific assets |
| `scripts/` | Portable development and release automation |
| `.github/` | GitHub collaboration and automation metadata |

## Development

Conductor requires Python 3.12 or newer for backend development.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make check
```

Run the control plane with `conductor-api`, then open `http://127.0.0.1:8080/docs`. The [getting-started guide](docs/getting-started.md) explains the process and configuration, while the [durable jobs guide](docs/jobs.md) demonstrates M2 in plain language.

The dashboard toolchain will be added when its first functional milestone begins.

## Status

M1 and M2 are complete: the control plane is runnable, and its job state is durable, duplicate-safe, tested, strictly typed, and checked in CI. M3 introduces worker processes and deterministic execution; the resource-aware scheduler and real AI runtimes remain deliberately out of scope until worker correctness is proven.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Conductor is available under the [MIT License](LICENSE).
