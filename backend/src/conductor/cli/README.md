# CLI

This package contains Conductor's command-line interface (CLI). The CLI is a
thin client: it sends requests to a running Conductor API and prints the API
response as readable JSON. It deliberately does **not** contain scheduling,
runtime, or database logic.

That separation matters. Whether an operator uses the CLI, the OpenAPI page,
or a future dashboard, every action follows the same API contract and reaches
the same service-layer rules.

Start with `main.py` to see how command-line arguments become API requests.
Then read `client.py` to see the small standard-library HTTP client and its
error translation.
