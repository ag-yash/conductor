# Run a local ONNX model

The ONNX adapter lets Conductor run a trusted local `.onnx` model file through
the same worker, scheduling, retry, and observability flow as fixture and
Ollama models.

## What ONNX means here

ONNX is a portable model format. The model is a computation graph stored in a
file; ONNX Runtime opens that file and evaluates the graph for tensor inputs.

Conductor’s first ONNX task is deliberately generic:

```text
task: tensor.infer
input: named numeric tensors
output: named numeric tensors, converted to JSON lists
```

That makes the adapter useful for compact classification, regression, and
embedding-style models without pretending that one request shape fits every AI
task.

## Register a model

Start with `examples/onnx-model.json`, but change `artifact` to an existing
local model file before registering it:

```json
{
  "id": "tiny-classifier",
  "display_name": "Tiny ONNX classifier",
  "runtime_kind": "onnx",
  "artifact": "/absolute/path/to/model.onnx",
  "supported_tasks": ["tensor.infer"],
  "expected_memory_bytes": 67108864,
  "idle_timeout_seconds": 300
}
```

Then register it:

```bash
conductor models register --file examples/onnx-model.json
```

## Submit tensor inference

The input keys must match the ONNX model’s input names. The values can be JSON
numbers or nested numeric lists. Conductor converts them to `float32` arrays
before calling ONNX Runtime.

```json
{
  "task": "tensor.infer",
  "model_id": "tiny-classifier",
  "input": {
    "inputs": {
      "features": [[1.0, 2.0, 3.0, 4.0]]
    }
  },
  "parameters": {}
}
```

If your model has several outputs, leave `parameters.output_names` absent to
return all of them. Or request a stable subset:

```json
"parameters": { "output_names": ["probabilities"] }
```

## Apple Silicon provider choice

The adapter asks ONNX Runtime which execution providers are available. On an
Apple Silicon installation that exposes `CoreMLExecutionProvider`, it prefers
CoreML and falls back to CPU. On another machine it uses CPU. This is a runtime
capability check, not a promise that every model will be accelerated: provider
support depends on the model graph and the installed ONNX Runtime build.

If the native runtime cannot open a model (for example, because the artifact is
corrupt or the environment prevents session creation), Conductor converts that
runtime-specific failure into one clear adapter error. This keeps the worker's
failure reporting consistent across all runtime types.

The same rule applies to bad tensor shapes and values. For example, a model that
expects an image tensor cannot accept a one-number JSON list. The native error
is preserved as context in Conductor's runtime failure rather than escaping as
an implementation-specific exception type.

## Why results are lists

ONNX Runtime returns NumPy arrays. A JSON API cannot directly send a NumPy
array, so the adapter converts each output with `tolist()`:

```text
NumPy array [[0.1, 0.9]] → JSON [[0.100000001, 0.899999976]]
```

The longer values are ordinary `float32` precision, not a model error. Compare
numeric outputs with a tolerance rather than exact decimal text.

## Code path to read

1. `runtime/onnx.py` validates the `tensor.infer` contract and owns sessions.
2. `runtime/manager.py` provides warm reuse and idle eviction just as it does
   for the other adapters.
3. `workers/runner.py` runs the adapter in the separate worker process.
4. `tests/test_onnx_runtime.py` proves input conversion, JSON-safe outputs, and
   unloading without checking in a model binary.
