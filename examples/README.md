# Example API payloads

These files are small, copyable request bodies for the `conductor` CLI. They
use the deterministic `fixture` runtime, so they work without downloading an AI
model or starting Ollama.

They are examples, not hidden configuration. Read them before using them and
change the identifiers if you want to keep multiple demo runs in one database.

`worker-resource-snapshot.json` is an example report for the current worker
process. The numbers are illustrative; replace them with measurements from your
own machine before using it to explain a real resource decision.
