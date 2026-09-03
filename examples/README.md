# Example API payloads

These files are small, copyable request bodies for the `conductor` CLI. Most
use the deterministic `fixture` runtime, so they work without downloading an AI
model or starting Ollama. `onnx-model.json` and `onnx-job.json` are templates
for `tensor.infer`; replace the model path with a real local `.onnx` file before
submitting them.

They are examples, not hidden configuration. Read them before using them and
change the identifiers if you want to keep multiple demo runs in one database.

`worker-resource-snapshot.json` is an example report for the current worker
process. The numbers are illustrative; replace them with measurements from your
own machine before using it to explain a real resource decision.
