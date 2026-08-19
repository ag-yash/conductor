# Documentation

These documents explain both **how to use Conductor** and **why it is designed this way**. You do not need to understand every distributed-systems term before starting.

## Recommended reading order

If this is your first time reading the project:

1. [`current-capabilities.md`](current-capabilities.md) — what you can run today versus what is planned.
2. [`vision.md`](vision.md) — the problem Conductor is designed to solve.
3. [`codebase-guide.md`](codebase-guide.md) — where code lives and how one request moves through it.
4. [`getting-started.md`](getting-started.md) — run the current system locally.
5. [`cli.md`](cli.md) — operate that running system from the terminal.
6. [`dashboard.md`](dashboard.md) — inspect the same system in a local browser.
7. [`jobs.md`](jobs.md) — understand durable jobs and idempotency.
8. [`workers.md`](workers.md) — understand workers, heartbeats, and process-instance IDs.
9. [`resource-telemetry.md`](resource-telemetry.md) — understand CPU/RAM snapshots and safe memory headroom.
10. [`standalone-worker.md`](standalone-worker.md) — run the real worker process and understand its current boundary.
11. [`scheduling.md`](scheduling.md) — understand how and why a worker is selected.
12. [`models-and-runtimes.md`](models-and-runtimes.md) — understand definitions, loaded state, and adapters.
13. [`benchmarks.md`](benchmarks.md) — measure warm runtime execution and read the summary.
14. [`state-machines.md`](state-machines.md) — understand legal status changes.
15. [`domain-model.md`](domain-model.md) — study the detailed objects and invariants.
16. [`persistence-and-concurrency.md`](persistence-and-concurrency.md) — understand transactions, repositories, and races.
17. [`testing.md`](testing.md) — understand how behavior and quality are verified.
18. [`architecture.md`](architecture.md) — connect all components and trade-offs.

You can keep [`glossary.md`](glossary.md) open while reading.

## Reference documents

- [`roadmap.md`](roadmap.md) lists completed and planned milestones.
- [`documentation-style.md`](documentation-style.md) defines how future documentation and comments should teach concepts.

## How to learn from a feature

For each feature, follow this loop:

```text
Read the plain-language document
              ↓
Trace the linked production files
              ↓
Read the integration test as an executable example
              ↓
Run the API flow locally
              ↓
Explain the design and one trade-off in your own words
```

Tests are especially useful: a test shows the starting situation, action, and expected behavior without requiring you to understand every implementation detail first.
