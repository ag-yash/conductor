# Getting started with Conductor

## What exists now (through the current M6 operator-experience slice)

Conductor currently provides:

- a FastAPI control plane with health checks and structured logs;
- durable SQLite jobs and execution attempts;
- worker registration, heartbeats, draining, and polling;
- deterministic slot-aware scheduling;
- persisted explanations showing why a worker was selected or rejected.
- trusted model definitions plus process-specific residency snapshots;
- fixture and Ollama runtime adapters, model loading, warm reuse, and idle eviction;
- runtime benchmark summaries through the worker API.
- a terminal CLI for the existing API, including models, jobs, worker operations,
  residencies, and benchmarks.
- a React dashboard with readiness and recent-state summaries, clickable job and
  worker investigation views, and a filterable, paginated queue explorer.

Use the fixture runtime to learn the full flow without downloading a model. Ollama
execution is available when you run Ollama locally and register an Ollama model.
See [`models-and-runtimes.md`](models-and-runtimes.md) and
[`benchmarks.md`](benchmarks.md) for those flows.

## Requirements

- Python 3.12 or newer
- macOS or Linux

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
conductor-api
```

What each command does:

- `python3.12 -m venv .venv` creates an isolated Python environment for this repository.
- `source .venv/bin/activate` makes the shell use that environment.
- `pip install -e '.[dev]'` installs Conductor in editable mode plus test/development tools.
- `conductor-api` starts the FastAPI process.

Editable mode means code changes are visible without reinstalling the package each time.

The server binds to `127.0.0.1:8080` by default, so it is not exposed to other machines.

Check that the process is alive:

```bash
curl -i http://127.0.0.1:8080/api/v1/health/live
```

Check that startup is complete:

```bash
curl -i http://127.0.0.1:8080/api/v1/health/ready
```

Both responses include an `X-Request-ID` header. This ID lets us connect one API response to the corresponding structured log entry when debugging concurrent requests.

### Liveness versus readiness

These endpoints answer different questions:

| Endpoint | Question |
| --- | --- |
| `/health/live` | Is the process alive and responding? |
| `/health/ready` | Has startup completed, including database setup? |

A process may be alive but not ready. For example, it could be running while a required migration is failing. A supervisor may restart an unresponsive process based on liveness, while a client should send work only when readiness succeeds.

## Configuration

Settings use environment variables beginning with `CONDUCTOR_`:

```bash
CONDUCTOR_PORT=9090 CONDUCTOR_LOG_LEVEL=DEBUG conductor-api
```

Invalid settings fail during startup instead of producing surprising runtime behavior.

Settings are typed definitions. For example, the port must be an integer between `1` and `65535`. Rejecting an invalid value during startup makes the configuration bug immediate and easy to find.

## Verify the repository

```bash
make check
```

This checks formatting, lint rules, static types, and tests. GitHub runs the same command for every pushed change.

The checks catch different kinds of problems:

| Check | Purpose | Example |
| --- | --- | --- |
| Black | Consistent formatting | Line wrapping |
| Ruff | Suspicious code and import style | Unused import |
| MyPy | Static type consistency | Returning `Any` where a job is expected |
| Pytest | Runtime behavior | Duplicate submission returns the same job |

Passing static checks does not prove runtime correctness, and passing tests does not guarantee consistent typing. We use all four because they protect different properties.

## Explore the current API

Open `http://127.0.0.1:8080/docs` in a browser. FastAPI generates an interactive OpenAPI page where you can inspect schemas and send requests.

Suggested learning path:

1. Call the health endpoints.
2. Submit and fetch a job using [`jobs.md`](jobs.md).
3. Read [`workers.md`](workers.md) and register a worker.
4. Follow [`scheduling.md`](scheduling.md) to inspect a placement decision.
5. Follow [`cli.md`](cli.md) to run the same flow from a terminal.
6. Follow [`dashboard.md`](dashboard.md) to view the same state in a browser.
7. Stop and restart the API, then confirm that the job still exists.

## Common setup problems

### `python3.12` is not found

The system Python on macOS may be older. Install Python 3.12 using your preferred package manager, then verify:

```bash
python3.12 --version
```

Do not lower Conductor’s declared Python version to match an old system Python. The virtual environment should use the project’s supported runtime.

### `conductor-api` is not found

Confirm the virtual environment is active and rerun:

```bash
python -m pip install -e '.[dev]'
```

### Readiness fails

Read the structured log with the matching `X-Request-ID`. Database-path or migration errors should appear during startup.

## What comes next

The remaining runtime work adds an ONNX adapter and deeper resource measurements.
M6 includes the CLI plus read-only dashboard summaries and investigation views;
resource charts and live updates remain planned. Check
[`current-capabilities.md`](current-capabilities.md) before relying on a target
feature described elsewhere.
