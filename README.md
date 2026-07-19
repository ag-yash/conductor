# Conductor

Conductor is an intelligent, local-first AI workload manager for developers. It will provide a unified way to schedule, run, and observe heterogeneous AI workloads while managing limited local compute and memory responsibly.

The first executable milestone provides the production-oriented control-plane shell: validated configuration, correlated structured logs, health checks, automated tests, and continuous integration. Job scheduling and AI execution are introduced in later milestones.

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

Run the control plane with `conductor-api`, then open `http://127.0.0.1:8080/api/v1/health/live`. The [M1 getting-started guide](docs/getting-started.md) explains the endpoints and configuration in plain language.

The dashboard toolchain will be added when its first functional milestone begins.

## Status

M1 is complete: the API shell is runnable, tested, strictly typed, and checked in CI. M2 introduces durable jobs and execution attempts; the scheduler and AI runtimes remain deliberately out of scope until that state model is proven.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Conductor is available under the [MIT License](LICENSE).
