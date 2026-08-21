# Command-line interface (CLI)

## Plain meaning

The `conductor` command is a terminal interface for a running Conductor API.
It lets you perform the same actions you could otherwise perform with curl or
the browser's `/docs` page, but with shorter commands and reusable JSON files.

It is **not** a second Conductor server. It does not schedule a job by itself,
load a model by itself, or open the SQLite database directly. It sends one HTTP
request to the control plane, then prints the response.

```text
Your terminal command
        |
        | HTTP request
        v
Running Conductor API
        |
        v
Services, runtime manager, and SQLite database
```

This boundary is intentional. A future dashboard can use exactly the same API,
so user interfaces cannot accidentally create different scheduling rules.

## Start the two processes

In the first terminal, start the API:

```bash
cd /Users/yash/Documents/Conductor
source .venv/bin/activate
conductor-api
```

In a second terminal, use the CLI:

```bash
cd /Users/yash/Documents/Conductor
source .venv/bin/activate
conductor health
```

The default API URL is `http://127.0.0.1:8080/api/v1`. The command works with a
different API address in either of two ways:

```bash
conductor --api-url http://127.0.0.1:9090/api/v1 health
CONDUCTOR_API_URL=http://127.0.0.1:9090/api/v1 conductor health
```

## A complete no-download demo

The `fixture` runtime is deterministic test infrastructure. It behaves like a
runtime—models load, become warm, execute, and unload—but it produces a stable
hash instead of calling a real AI model. This lets you demonstrate Conductor's
control-plane behaviour on any laptop.

Register a model and a worker:

```bash
conductor models register --file examples/fixture-model.json
conductor workers register --file examples/local-worker.json
```

Submit a durable job. The idempotency key means you can safely retry the exact
same command after a network problem without creating a second job:

```bash
conductor jobs submit \
  --file examples/fixture-job.json \
  --idempotency-key fixture-demo-job-1
```

The commands below remain useful for learning the lease and start transitions.
For ordinary local execution, `conductor-worker` now automates polling,
heartbeats, resource reports, local runtime execution, and result reporting;
see [`standalone-worker.md`](standalone-worker.md).

```bash
# Copy the attempt ID from this response.
conductor workers next-lease --worker-id demo-worker --instance-id process-a

conductor workers start --worker-id demo-worker --instance-id process-a ATTEMPT_ID
```

Now inspect what happened:

```bash
conductor jobs list
conductor workers residencies --worker-id demo-worker --instance-id process-a
conductor workers report-resources \
  --worker-id demo-worker \
  --instance-id process-a \
  --file examples/worker-resource-snapshot.json
```

Run a warm-runtime benchmark using the same model:

```bash
conductor benchmarks run \
  --worker-id demo-worker \
  --instance-id process-a \
  --file examples/fixture-benchmark.json

conductor benchmarks list --worker-id demo-worker --instance-id process-a
```

## Command groups

| Group | Typical commands | What it operates |
| --- | --- | --- |
| `health` | `conductor health`, `conductor health live` | API liveness and readiness |
| `models` | `list`, `get MODEL_ID`, `register --file FILE` | Trusted model definitions |
| `jobs` | `list`, `submit`, `get`, `cancel`, `decisions` | Durable jobs and scheduling history |
| `workers` | `register`, `heartbeat`, `drain`, `next-lease`, `start`, `complete`, `residencies`, `report-resources`, `resource-snapshots`, `evict-idle` | One registered worker process |
| `benchmarks` | `run`, `list` | Persisted warm-runtime timing summaries |

Use `--help` at every level to discover the exact arguments:

```bash
conductor --help
conductor workers --help
conductor benchmarks run --help
```

## Why commands use JSON files

A job or a model has nested fields such as `input`, `parameters`, and
`supported_tasks`. Passing nested JSON through shell quotes is difficult to
read and easy to break. A JSON file is clearer, can be reviewed in Git, and can
be sent again during a demo.

For example, `examples/fixture-job.json` is the body of `POST /api/v1/jobs`.
The CLI reads it, validates that it is a JSON object, and sends it unchanged.
FastAPI then performs the authoritative schema validation.

## Errors

The CLI prints expected operational failures to stderr and returns exit code
`1`; successful commands return `0`.

Examples:

- **Cannot reach Conductor**: start `conductor-api`, then retry.
- **HTTP 422**: the JSON body does not match the API schema; the response gives
  the invalid field.
- **HTTP 409**: often means an old worker process instance tried to operate a
  worker after it restarted. Re-register or use the current `--instance-id`.
- **No content** from `next-lease`: there is currently no eligible job. This is
  normal, not an error.

## Code path to study

1. `backend/src/conductor/cli/main.py` parses the command and selects an API
   path.
2. `backend/src/conductor/cli/client.py` sends JSON over HTTP and turns transport
   errors into operator-friendly messages.
3. FastAPI routes in `backend/src/conductor/api/` validate the request.
4. Services and domain objects enforce the actual Conductor rules.
5. `tests/test_cli.py` proves commands map to the intended HTTP request without
   starting a server.

The key idea is **thin client, thick control plane**: interfaces are simple;
the important rules live in one authoritative backend.
