# Persistence, transactions, and concurrency

This document explains how Conductor keeps state safe when processes restart or operations happen at the same time.

## In-memory state versus durable state

An ordinary Python dictionary disappears when the process exits:

```python
jobs = {"J1": "queued"}
```

SQLite stores the same information in a file. When Conductor restarts, it reopens that file and continues.

This is why the database is the source of truth. An in-memory queue may later make scheduling faster, but losing that queue must never lose accepted work.

## Why SQLite is enough for V1

SQLite provides:

- durable local storage;
- real transactions;
- uniqueness constraints;
- indexes;
- no separate database server;
- a simple setup for contributors.

Its main limitation is write concurrency: SQLite permits fewer simultaneous writers than a server database such as PostgreSQL. Conductor V1 runs on one laptop with one control-plane process, so this trade-off is appropriate.

The repository interfaces make a later database change possible, but we should switch only after measurements show SQLite is a bottleneck.

## Repository pattern

A repository gives domain-focused names to storage operations:

```python
job = jobs.get(job_id)
jobs.add(new_job)
jobs.update(changed_job, expected_version=old_version)
```

The service does not construct SQL. The SQLite repository translates between:

```text
domain Job ↔ SQLModel JobRecord ↔ SQLite row
```

Benefits:

- services are readable in business terms;
- SQL stays in one layer;
- database records cannot bypass domain rules accidentally;
- tests can replace the storage implementation if needed.

Cost:

- mapping code must be maintained;
- a very small application has more files than direct SQL in routes.

Conductor accepts that cost because concurrency and lifecycle rules are central to the product.

## Repository ports

`services/ports.py` contains Python `Protocol` definitions. A protocol says which methods an implementation must provide.

```text
JobService depends on JobRepository
                       ↑
             SqlJobRepository implements it
```

This is the dependency inversion principle: high-level policy depends on a small abstraction rather than a low-level database library.

## Unit of work

A unit of work groups repositories around one database session and transaction.

For job leasing:

```text
BEGIN TRANSACTION
  insert execution attempt
  update job to assigned
  insert scheduling explanation
COMMIT
```

If the explanation insert fails, the entire transaction rolls back. The system does not leave behind a half-assigned job.

In code, the `with` block defines the transaction’s lifetime:

```python
with uow_factory() as uow:
    # read and write through uow.jobs, uow.attempts, ...
    uow.commit()
```

If an exception escapes, the unit of work rolls back and closes the session.

## Atomicity

Atomic means “all or nothing.”

Bank-transfer example:

```text
subtract ₹100 from account A
add ₹100 to account B
```

Saving only the first operation loses money. Both belong in one transaction.

Conductor’s equivalent is:

```text
create attempt A1
assign job J1 to A1
```

Saving only one would create contradictory state.

## Optimistic concurrency control

Conductor’s mutable domain objects carry a version number.

```text
job J1, version 3, status queued
```

Two operations read version `3`:

```text
Worker assignment → wants assigned/version 4
User cancellation → wants cancelled/version 4
```

The database update includes `WHERE version = 3`. The first commit succeeds. The second affects zero rows because the stored version is already `4`.

The second operation receives a conflict and must reread state.

Why not lock the row first?

- conflicts are expected to be uncommon;
- holding locks while application logic runs reduces concurrency;
- version checks are simple and explicit.

The trade-off is that callers must handle a conflict and possibly retry.

## Uniqueness constraints

Some rules must be protected by the database, not only by Python checks.

Example:

```text
idempotency_key must be unique
```

Two requests can both check “the key does not exist” before either inserts it. A database uniqueness constraint ensures only one insert can commit. The losing request then loads the winner and decides whether it is a safe replay or a conflict.

This is a classic check-then-act race:

```text
Request A checks → absent
Request B checks → absent
Request A inserts → success
Request B inserts → uniqueness error
```

## Migrations

A migration changes database structure in a numbered, repeatable way.

Current history:

- `0001`: jobs and attempts;
- `0002`: workers;
- `0003`: scheduling decisions.
- `0004`: model definitions;
- `0005`: job results and safe failure messages;
- `0006`: model-residency snapshots;
- `0007`: benchmark summaries.

On startup, Conductor applies missing migrations before readiness becomes true. That prevents the API from accepting work against an outdated schema.

## Indexes

An index is an additional data structure that makes selected lookups faster at the cost of storage and slightly slower writes.

Examples:

- jobs indexed by status and creation time help find queued work;
- decisions indexed by job and creation time help show one job’s history.
- benchmarks indexed by worker/model and creation time help compare recent runs.

We add indexes for actual query patterns rather than indexing every column.

## Questions to check your understanding

1. Why can an in-memory queue not be the only source of truth?
2. What inconsistent state does the leasing transaction prevent?
3. How does a version column detect a race?
4. Why is a Python “does this key exist?” check insufficient for uniqueness?
5. What evidence might justify moving from SQLite to PostgreSQL?
