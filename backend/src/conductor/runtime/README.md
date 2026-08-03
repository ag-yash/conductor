# Runtime

This package defines one common `load → invoke → unload` contract for local AI runtimes.

- `base.py` contains the runtime-neutral protocol and result.
- `fixture.py` provides predictable execution for tests without a model download.
- `ollama.py` translates Conductor's `text.generate` task into Ollama's local HTTP API.
- `manager.py` loads an adapter on first use and reuses it for warm requests.

The manager's residency cache is process-local on purpose. A loaded model is a
memory object inside one worker process, so it cannot be trusted after that
process restarts. Durable model definitions and job results remain in SQLite.

After a successful execution, the worker persists the manager's latest residency
snapshot. Calling the worker's idle-eviction operation unloads eligible adapters
and then removes those snapshots from SQLite.

Runtime-specific request shapes stay here; the scheduler and domain must not depend on Ollama.
