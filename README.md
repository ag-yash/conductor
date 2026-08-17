# Conductor

Conductor is an intelligent, local-first AI workload manager for developers. It
provides a unified way to schedule, run, and observe selected local AI workloads
while managing model residency responsibly. The complete `v1.0.0` target expands
this with richer dashboard views, an ONNX runtime, and deeper resource-aware scheduling.

Conductor currently provides a local control plane with durable SQLite jobs,
explainable worker scheduling, worker leases, trusted model definitions, fixture
and Ollama runtime adapters, warm-model residency, idle eviction, and recorded
runtime benchmarks, a terminal CLI, and a local dashboard with summary, detail,
and queue-investigation views. See [the current-capabilities guide](docs/current-capabilities.md)
for a precise implemented-versus-planned matrix.

## Product principles

- **Local-first:** useful on a developer laptop without cloud infrastructure.
- **Runtime-agnostic:** the control plane is not coupled to one model provider.
- **Resource-aware:** model lifecycle decisions account for local constraints; richer scheduler inputs are planned.
- **Observable:** jobs, workers, models, and benchmark results are inspectable through the API.
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

Run the control plane with `conductor-api`, then open `http://127.0.0.1:8080/docs`,
use `conductor health`, or start the local browser dashboard. The
[getting-started guide](docs/getting-started.md) explains the process and configuration;
[`docs/cli.md`](docs/cli.md) and [`docs/dashboard.md`](docs/dashboard.md) give runnable demos.

## Status

M1–M5 are complete: the control plane provides durable jobs, workers, explainable
scheduling, model lifecycle management, runtimes, and benchmarks. M6 is in
progress: the CLI and read-only dashboard investigation views are available;
resource charts and live updates remain planned.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Conductor is available under the [MIT License](LICENSE).
