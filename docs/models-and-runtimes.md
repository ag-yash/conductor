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

## Current M5 boundary

This first slice provides:

- durable model-definition registration;
- model-residency domain rules;
- a common runtime adapter protocol;
- deterministic fixture execution;
- Ollama load, generate, metrics, and unload translation.

The next slice connects these adapters to the long-running worker loop, persists residency reports, records results on jobs, and adds idle eviction.

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

## Questions to check your understanding

1. Why does a registered definition not imply a loaded model?
2. Why is residency tied to `worker_instance_id`?
3. What does the adapter pattern prevent from leaking into the scheduler?
4. Why is deterministic fixture execution valuable?
5. Why must a model with active executions reject unloading?
