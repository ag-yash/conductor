# Documentation style for Conductor

This file defines how Conductor should be explained in documentation and code comments.

## Intended reader

Write for a software developer who:

- has built backend services before;
- understands basic HTTP, databases, and Python;
- may not yet have implemented schedulers, leases, state machines, repository ports, or optimistic concurrency;
- wants to understand the reasoning, not merely copy commands.

## Required explanation order

When introducing a concept, use this order:

1. **Concrete example** — describe a situation a developer can picture.
2. **Plain-language meaning** — explain the idea without assuming specialist vocabulary.
3. **Technical term** — name the concept after the meaning is clear.
4. **How Conductor uses it** — link the idea to real files or request flows.
5. **Why we chose it** — explain the benefit.
6. **Trade-off or alternative** — explain what the decision costs and what else could have been used.
7. **Failure example** — show the bug or operational problem the concept prevents.

Repeating an important idea is acceptable when the second explanation appears in a different context.

## Code-comment rules

Comments should explain:

- why an operation must be atomic;
- why a state transition is restricted;
- why stale worker messages are rejected;
- why a query includes or excludes particular states;
- why one architecture boundary exists;
- why a simple-looking line protects a concurrency invariant.

Comments should not merely translate syntax:

```python
# Bad: increment version by one
version = version + 1

# Good: changing the version makes a concurrent writer using the old snapshot fail
version = version + 1
```

## Words that need an explanation

Do not use these as if their meaning is obvious:

- aggregate
- invariant
- idempotency
- lease
- epoch or process-instance ID
- optimistic concurrency
- unit of work
- repository port
- canonical representation
- deterministic
- eventual consistency
- backpressure
- model residency

Explain them locally or link to [`glossary.md`](glossary.md).

## Keeping documents current

Every milestone should update:

- [`roadmap.md`](roadmap.md), including its completion marker;
- [`codebase-guide.md`](codebase-guide.md), including the recommended reading order;
- the relevant feature document;
- [`glossary.md`](glossary.md) when new vocabulary appears;
- comments around new non-obvious correctness logic.

