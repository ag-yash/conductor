# Runtime benchmarks

A benchmark answers a narrow question:

> How long did this configured model take to run this task on this worker process?

It does **not** answer “Which model is smarter?” or “How much RAM did the laptop
use overall?” Those require separate quality evaluations and resource sampling.

## Why warmups exist

The first request to a model is often slower because the runtime may need to load
weights, allocate memory, or initialize a backend. That is called a **cold start**.

Conductor separates that first work from measured samples:

```text
warmup 1 → may load the model; not included in timings
sample 1 → timed
sample 2 → timed
sample 3 → timed
```

The resulting summary describes warm, steady-state execution more fairly.

## API flow

First register a fixture model and a worker. The fixture runtime needs no model
download, so it is the best way to learn the protocol.

```bash
curl -X POST http://127.0.0.1:8080/api/v1/models \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "fixture-text",
    "display_name": "Fixture text runtime",
    "runtime_kind": "fixture",
    "artifact": "fixture://text",
    "supported_tasks": ["text.generate"],
    "expected_memory_bytes": 1,
    "idle_timeout_seconds": 300
  }'

curl -X POST http://127.0.0.1:8080/api/v1/workers/register \
  -H 'Content-Type: application/json' \
  -d '{
    "worker_id": "laptop-worker",
    "worker_instance_id": "process-1",
    "supported_tasks": ["text.generate"],
    "max_parallel_jobs": 1
  }'
```

Then request a benchmark:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/workers/laptop-worker/benchmarks \
  -H 'Content-Type: application/json' \
  -H 'Worker-Instance-ID: process-1' \
  -d '{
    "model_id": "fixture-text",
    "task": "text.generate",
    "input": {"prompt": "Explain warm models."},
    "parameters": {"temperature": 0.2},
    "warmup_iterations": 1,
    "measurement_iterations": 3
  }'
```

The summary contains:

| Field | Plain meaning |
| --- | --- |
| `warmup_iterations` | Runs intentionally excluded from timing statistics |
| `measurement_iterations` | Number of timed runs |
| `total_wall_time_ms` | Sum of all timed elapsed durations |
| `mean_wall_time_ms` | Average elapsed duration per timed run |
| `min_wall_time_ms` / `max_wall_time_ms` | Fastest and slowest timed runs |
| `mean_runtime_metrics` | Average numeric metrics reported by the runtime itself |

For Ollama, runtime metrics may include values such as `eval_count` and
`eval_duration`. The runtime controls their units and availability. Conductor
stores them as reported and labels its own timing fields explicitly in milliseconds.

## What happens in the code

```text
POST /workers/{id}/benchmarks
       ↓
api/workers.py validates bounded input
       ↓
WorkerService verifies the current worker and model definition
       ↓
RuntimeManager runs warmups, then timed samples
       ↓
BenchmarkSummary calculates min/mean/max wall-clock timing
       ↓
SQLite stores one immutable benchmark summary
```

The summary is append-only history. Running a new benchmark creates a new row
instead of overwriting an older result, because environment conditions can change.

## Comparing results responsibly

Use the same model artifact, task, input, parameters, worker, and number of
warmups when comparing two summaries. Otherwise you are changing more than one
variable and the comparison becomes ambiguous.

Example of a fair comparison:

```text
Same prompt + same Qwen artifact + same laptop + 1 warmup + 5 samples
```

Example of an unfair comparison:

```text
Short prompt on one model versus long prompt on another model
```

## Failure behavior

If the runtime fails during a benchmark, Conductor records the latest residency
state—often `FAILED`—but does not create a successful summary. The API returns a
runtime error instead of mixing partial timings with a completed benchmark.

This is deliberate: a benchmark is only comparable when all measured iterations
finish successfully.
