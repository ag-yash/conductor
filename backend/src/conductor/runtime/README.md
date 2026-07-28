# Runtime

This package defines one common `load → invoke → unload` contract for local AI runtimes.

- `base.py` contains the runtime-neutral protocol and result.
- `fixture.py` provides predictable execution for tests without a model download.
- `ollama.py` translates Conductor's `text.generate` task into Ollama's local HTTP API.

Runtime-specific request shapes stay here; the scheduler and domain must not depend on Ollama.
