# Conductor

Conductor is an intelligent, local-first AI workload manager for developers. It will provide a unified way to schedule, run, and observe heterogeneous AI workloads while managing limited local compute and memory responsibly.

This repository currently contains the production-oriented foundation for Conductor. Application behavior will be introduced through reviewed milestones; the initial scaffold deliberately contains no business logic.

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
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make check
```

The dashboard toolchain will be added when its first functional milestone begins.

## Status

The repository foundation and V1 design package are complete. There is no application logic yet. The next milestone introduces the executable control-plane shell and its first tested health endpoint.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Conductor is available under the [MIT License](LICENSE).
