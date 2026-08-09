# How Conductor is tested

Tests are executable examples of expected behavior. They help us change implementation details without accidentally changing the product contract.

## Backend and dashboard quality gates

`make check` runs:

```text
Black → Ruff → MyPy → Pytest with coverage
```

| Tool | What it checks | What it does not prove |
| --- | --- | --- |
| Black | Consistent formatting | Correct behavior |
| Ruff | Common code problems and import/style rules | Runtime correctness |
| MyPy | Whether declared types agree | That every value is logically correct |
| Pytest | Behavior for written scenarios | Behavior for scenarios nobody wrote |

All gates matter because they find different classes of mistakes.

The browser application has its own checks:

```text
npm run lint → npm run build
```

The first command checks TypeScript and React code for common mistakes. The
second runs TypeScript's compiler and asks Vite to produce the actual browser
bundle. A dashboard can look correct in source code but still fail to compile;
the build step catches that before a browser user does.

GitHub Actions runs both the Python gates and these dashboard gates on every
pull request. The two applications have different toolchains, so keeping their
checks explicit makes a failed pipeline easier to understand.

## Unit tests versus integration tests

A unit test exercises a small piece without starting the whole application.

Example:

```text
Given a queued Job
When assign(attempt_id) is called
Then a new assigned Job is returned
```

An integration test exercises several layers together.

Example:

```text
HTTP request
  → FastAPI validation
  → service
  → domain
  → repository
  → temporary SQLite database
  → HTTP response
```

Conductor uses both. Pure domain and scheduler rules benefit from fast unit tests; API flows prove the layers are wired together correctly.

## Test isolation

Each API test receives a temporary SQLite database through the `app_settings` fixture in `tests/conftest.py`.

```text
test A → /tmp/.../conductor.db
test B → /tmp/.../conductor.db
```

One test cannot accidentally depend on a job created by another test. This property is test isolation.

Without isolation, tests might pass in one order and fail in another.

## Fixtures

A Pytest fixture prepares reusable test state.

The `client` fixture:

1. creates test settings;
2. builds an isolated FastAPI application;
3. starts its lifespan, including migrations;
4. gives the test an HTTP client;
5. shuts the application down afterward.

Fixtures reduce repeated setup while keeping each test explicit about what it needs.

## Arrange–Act–Assert

Most tests follow three phases:

```python
# Arrange: create workers and a queued job

# Act: ask worker-b for a lease

# Assert: worker-b receives the job and the reason is recorded
```

When a test is confusing, label these phases mentally and identify the user-visible rule it proves.

## Important current test groups

| File | Behavior protected |
| --- | --- |
| `test_health.py` | Liveness and readiness contracts |
| `test_logging.py` | Structured request correlation |
| `test_settings.py` | Typed configuration |
| `test_job_domain.py` | Legal job and attempt transitions |
| `test_jobs_api.py` | Submission, idempotency, listing, cancellation, restart durability |
| `test_workers_api.py` | Registration, heartbeat, restart identity, leasing, draining |
| `test_scheduling_api.py` | Capacity-aware selection and persisted explanation |
| `test_runtime_adapters.py` | Fixture determinism and Ollama request/error translation without a live server |
| `test_model_domain.py` | Model definition and residency lifecycle rules |

`test_workers_api.py` also covers the runtime execution flow, persisted residency,
idle eviction, and benchmark history. It is an integration test because one HTTP
request travels through validation, service logic, runtime coordination, SQLite,
and the response schema.

The dashboard's initial behaviour is simple enough to verify through its lint
and production build: it is a typed read-only client over existing APIs. The
new `GET /workers` backend contract is protected by
`test_operator_can_list_current_registered_workers` in `test_workers_api.py`.
Later, when the dashboard gains filters, write actions, or live updates, it will
also receive browser-level interaction tests.

## Testing concurrency rules

Concurrency bugs can be difficult to reproduce with timing alone. Conductor encodes many protections as deterministic state/version checks.

Instead of hoping two threads collide during a test, a test can:

1. read version `2`;
2. perform one update to version `3`;
3. attempt another update expecting version `2`;
4. assert that it is rejected.

Later milestones will add explicit failure-injection tests for expired leases and worker loss.

## Coverage

Coverage reports which production lines were executed by tests. It is useful for finding completely untested branches.

High coverage does not guarantee strong tests. A test could execute a line without checking the important result. We combine coverage with scenario-focused assertions.

## Reading a failing CI run

The quality gate stops at the first failed stage:

```text
formatting failure → later checks do not run yet
lint passes, MyPy fails → tests have not run yet
all static checks pass, Pytest fails → runtime behavior is wrong
```

Fix the reported root cause, rerun the entire gate, and continue until all stages pass.

## How to add a test for a feature

Include:

- the normal success path;
- invalid input;
- invalid state transition;
- repeated/idempotent operation when relevant;
- stale or concurrent update when relevant;
- restart durability when state is persisted;
- a failure that proves the feature does not corrupt related state.

## Questions to check your understanding

1. Why does every API test get a separate database?
2. What does MyPy catch that Pytest may not?
3. Why is 100% coverage not proof of correctness?
4. When should a scheduler rule use a unit test?
5. What three phases help you read an unfamiliar test?
