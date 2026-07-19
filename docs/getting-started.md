# Getting started with the M1 control plane

## What exists now

M1 is the smallest runnable version of Conductor. It does not run AI jobs yet. It proves that the control-plane process can start with validated configuration, identify requests, produce machine-readable logs, and report whether it is healthy.

In plain English: this is the reliable shell that later job scheduling and workers will run inside.

## Requirements

- Python 3.12 or newer
- macOS or Linux

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
conductor-api
```

The server binds to `127.0.0.1:8080` by default, so it is not exposed to other machines.

Check that the process is alive:

```bash
curl -i http://127.0.0.1:8080/api/v1/health/live
```

Check that startup is complete:

```bash
curl -i http://127.0.0.1:8080/api/v1/health/ready
```

Both responses include an `X-Request-ID` header. This ID lets us connect one API response to the corresponding structured log entry when debugging concurrent requests.

## Configuration

Settings use environment variables beginning with `CONDUCTOR_`:

```bash
CONDUCTOR_PORT=9090 CONDUCTOR_LOG_LEVEL=DEBUG conductor-api
```

Invalid settings fail during startup instead of producing surprising runtime behavior.

## Verify the repository

```bash
make check
```

This checks formatting, lint rules, static types, and tests. GitHub runs the same command for every pushed change.

## What comes next

M2 adds durable jobs and attempts. The scheduler, workers, and AI runtime integrations deliberately remain absent until their underlying state rules are implemented and tested.
