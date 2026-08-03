# Models, residency, and runtime adapters

M5 introduces the boundary between Conductor's coordination logic and real AI software.

## Three different ideas

These terms sound similar but represent different things:

| Idea | Example | Lifetime |
| --- | --- | --- |
| Model definition | “Use `qwen2.5:1.5b` through Ollama” | Durable configuration |
| Model residency | “Qwen is loaded in worker-a/process-b” | One worker process |
| Runtime adapter | Code translating Conductor calls into Ollama requests | Application code |

### Model definition

A model definition is trusted metadata:

```json
{
  "id": "qwen-small",
  "runtime_kind": "ollama",
  "artifact": "qwen2.5:1.5b",
  "supported_tasks": ["text.generate"],
  "expected_memory_bytes": 2000000000,
  "idle_timeout_seconds": 300
}
```

It does not mean the model is currently in memory. Definitions survive application restarts because SQLite stores them.

### Model residency

Residency tracks loaded state inside one exact worker process:

```text
ABSENT → LOADING → READY → UNLOADING → ABSENT
                    ↓
                  FAILED
```

If the worker restarts, its memory disappears. A residency associated with the old `worker_instance_id` cannot be reused.

### Runtime adapter

Conductor calls:

```text
adapter.load(model)
adapter.invoke(model, task, input, parameters)
adapter.unload(model)
```

The Ollama adapter translates those calls into local HTTP JSON. A future ONNX adapter will translate the same contract into ONNX Runtime calls.

This is the adapter pattern: Conductor depends on its own small interface while each integration handles external details.

## Why a fixture runtime exists

The fixture runtime is not fake production AI. Its purpose is deterministic systems testing.

It:

- requires a model to be loaded before invocation;
- validates task support;
- hashes canonical input into a repeatable output;
- unloads without downloading anything.

This lets tests prove worker failure, retry, scheduling, and lifecycle behavior on any development machine or CI runner.

## Ollama lifecycle mapping

Ollama's official API supports:

- `POST /api/generate` with `stream: false` for one JSON response;
- an empty prompt and negative `keep_alive` to preload and retain a model;
- `keep_alive: 0` to unload it.

Conductor keeps these details inside `runtime/ollama.py`.

References:

- [Ollama generate API](https://docs.ollama.com/api/generate)
- [Ollama model lifecycle FAQ](https://docs.ollama.com/faq)

## Why not import the official Ollama Python library?

The first adapter uses a tiny injected JSON transport:

- the required API surface is small;
- tests can replace network access with `FakeTransport`;
- Conductor's runtime contract remains visible;
- an external client package can be adopted later if it provides measured value.

The trade-off is that we own basic request/error translation.

## The worker execution flow

After a worker receives a lease, it now performs this sequence:

```text
lease → start → execute → result/failure
                    ↓
             load model if cold
                    ↓
             reuse it if warm
```

For example, a fixture job goes through:

1. `POST /workers/demo-worker/leases/next` reserves the job.
2. `POST .../start` changes the attempt and job to `running`.
3. `POST .../execute` asks `RuntimeManager` to load `qwen-demo` if needed.
4. The fixture adapter returns a deterministic digest.
5. The result is saved in the job row and the attempt becomes `succeeded`.

The `RuntimeManager` keeps residency in process memory because loaded model memory
does not survive a worker restart. SQLite stores the durable model definition and
job result; the manager stores the short-lived “currently loaded here” fact.

If the same worker executes another job for the same model, the adapter is reused
without another `load` call. This is the first warm-model optimization.

## Persisted residency and eviction

After an execution finishes, Conductor saves a snapshot like this:

```text
model: qwen-demo
worker: demo-worker / process-a
status: ready
active executions: 0
last used: 10:32:05
```

This row is not the model itself and it is not an execution history. It is an
operator-friendly answer to: “Which worker currently has this model loaded?”

The snapshot is updated after execution and disappears after successful eviction.
If the worker process restarts, its old memory is gone; the old process identity
prevents that stale residency from being reused.

Idle eviction compares `last_used_at` with the model's configured timeout:

```text
last_used_at + idle_timeout_seconds <= now
                         ↓
                  unload the model
```

Eviction first enters the `UNLOADING` state and calls the adapter's `unload` method.
Only after that succeeds does Conductor remove the persisted snapshot. This avoids
claiming that a model is gone before the runtime has released it.

## Current M5 boundary

This first slice provides:

- durable model-definition registration;
- model-residency domain rules;
- a common runtime adapter protocol;
- deterministic fixture execution;
- Ollama load, generate, metrics, and unload translation.
- worker execution through the fixture runtime;
- durable job results and safe runtime failure messages;
- process-local warm-model reuse;
- persisted residency snapshots and an idle-eviction endpoint.

Memory-pressure eviction and periodic background eviction remain future hardening
work; the current endpoint makes the policy observable and testable first.

## Read the code in this order

1. `domain/model.py`
2. `runtime/base.py`
3. `runtime/fixture.py`
4. `runtime/ollama.py`
5. `services/models.py`
6. `api/models.py`
7. `tests/test_model_domain.py`
8. `tests/test_runtime_adapters.py`
9. `tests/test_models_api.py`
10. `runtime/manager.py`
11. `tests/test_workers_api.py`

## Questions to check your understanding

1. Why does a registered definition not imply a loaded model?
2. Why is residency tied to `worker_instance_id`?
3. What does the adapter pattern prevent from leaking into the scheduler?
4. Why is deterministic fixture execution valuable?
5. Why must a model with active executions reject unloading?
