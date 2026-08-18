"""Parse `conductor` commands and forward them to the local control plane."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

from conductor.cli.client import CliError, HttpApiClient

DEFAULT_API_URL = "http://127.0.0.1:8080/api/v1"


class ApiClient(Protocol):
    """The small part of the HTTP client needed by command handlers."""

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any: ...


def _add_payload_file_argument(parser: argparse.ArgumentParser) -> None:
    """Use JSON files so complex API payloads stay explicit and reproducible."""

    parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Path to a JSON object matching the API request body.",
    )


def _add_worker_identity_arguments(parser: argparse.ArgumentParser) -> None:
    """Worker identity has two parts because a restarted process is distinct."""

    parser.add_argument("--worker-id", required=True, help="Logical worker identifier.")
    parser.add_argument(
        "--instance-id",
        required=True,
        help="Unique identifier for this running worker process instance.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI grammar without performing network or file operations."""

    parser = argparse.ArgumentParser(
        prog="conductor",
        description="Operate a running local Conductor control plane.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("CONDUCTOR_API_URL", DEFAULT_API_URL),
        help=("Conductor API base URL. Defaults to CONDUCTOR_API_URL or " f"{DEFAULT_API_URL}."),
    )
    groups = parser.add_subparsers(dest="group", required=True)

    health = groups.add_parser("health", help="Check whether the API is alive or ready.")
    health.add_argument("check", choices=("live", "ready"), nargs="?", default="ready")

    models = groups.add_parser("models", help="Register and inspect model definitions.")
    model_actions = models.add_subparsers(dest="action", required=True)
    model_actions.add_parser("list", help="List model definitions.")
    model_get = model_actions.add_parser("get", help="Get one model definition.")
    model_get.add_argument("model_id")
    model_register = model_actions.add_parser("register", help="Register a model from JSON.")
    _add_payload_file_argument(model_register)

    jobs = groups.add_parser("jobs", help="Submit and inspect durable jobs.")
    job_actions = jobs.add_subparsers(dest="action", required=True)
    job_list = job_actions.add_parser("list", help="List jobs.")
    job_list.add_argument("--status", help="Optional job status filter, for example queued.")
    job_list.add_argument("--limit", type=int, default=50, help="Maximum jobs to return (1-100).")
    job_list.add_argument("--offset", type=int, default=0, help="Number of matching jobs to skip.")
    job_submit = job_actions.add_parser("submit", help="Submit a job from JSON.")
    _add_payload_file_argument(job_submit)
    job_submit.add_argument(
        "--idempotency-key",
        required=True,
        help="Stable key that makes repeating this submit safe.",
    )
    for action, help_text in (
        ("get", "Get one job."),
        ("cancel", "Cancel one queued job."),
        ("decisions", "Show recorded scheduling decisions for one job."),
    ):
        action_parser = job_actions.add_parser(action, help=help_text)
        action_parser.add_argument("job_id")

    workers = groups.add_parser("workers", help="Operate a registered worker process.")
    worker_actions = workers.add_subparsers(dest="action", required=True)
    worker_register = worker_actions.add_parser("register", help="Register a worker from JSON.")
    _add_payload_file_argument(worker_register)
    for action, help_text in (
        ("heartbeat", "Send a worker heartbeat."),
        ("drain", "Stop a worker from receiving new jobs."),
        ("next-lease", "Ask for the next eligible job lease."),
        ("residencies", "List model residency snapshots."),
        ("resource-snapshots", "List saved host and process resource measurements."),
        ("evict-idle", "Unload idle resident models."),
    ):
        action_parser = worker_actions.add_parser(action, help=help_text)
        _add_worker_identity_arguments(action_parser)
    resource_report = worker_actions.add_parser(
        "report-resources", help="Record one worker resource measurement from JSON."
    )
    _add_worker_identity_arguments(resource_report)
    _add_payload_file_argument(resource_report)
    for action, help_text in (
        ("start", "Mark a leased attempt as running."),
        ("complete", "Mark a running attempt complete without runtime execution."),
        ("execute", "Run a started attempt through its configured runtime."),
    ):
        action_parser = worker_actions.add_parser(action, help=help_text)
        _add_worker_identity_arguments(action_parser)
        action_parser.add_argument("attempt_id")

    benchmarks = groups.add_parser("benchmarks", help="Run and inspect warm-runtime benchmarks.")
    benchmark_actions = benchmarks.add_subparsers(dest="action", required=True)
    benchmark_run = benchmark_actions.add_parser("run", help="Run a benchmark from JSON.")
    _add_worker_identity_arguments(benchmark_run)
    _add_payload_file_argument(benchmark_run)
    benchmark_list = benchmark_actions.add_parser("list", help="List saved benchmark summaries.")
    _add_worker_identity_arguments(benchmark_list)
    benchmark_list.add_argument(
        "--limit", type=int, default=20, help="Maximum summaries to return."
    )
    return parser


def _read_payload(path: Path) -> dict[str, Any]:
    """Read one JSON object, with errors that tell an operator what to fix."""

    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CliError(f"Payload file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise CliError(f"Payload file is not valid JSON: {path} ({error.msg})") from error
    if not isinstance(decoded, dict):
        raise CliError(f"Payload file must contain one JSON object: {path}")
    return decoded


def _worker_headers(args: argparse.Namespace) -> dict[str, str]:
    return {"Worker-Instance-ID": str(args.instance_id)}


def _query(**values: object | None) -> str:
    """Build a URL query string while leaving absent optional filters out."""

    active_values = {key: str(value) for key, value in values.items() if value is not None}
    return f"?{urlencode(active_values)}" if active_values else ""


def dispatch(args: argparse.Namespace, client: ApiClient) -> Any:
    """Map parsed operator intent onto an existing, documented HTTP contract."""

    if args.group == "health":
        return client.request("GET", f"health/{args.check}")
    if args.group == "models":
        if args.action == "list":
            return client.request("GET", "models")
        if args.action == "get":
            return client.request("GET", f"models/{args.model_id}")
        return client.request("POST", "models", payload=_read_payload(args.file))
    if args.group == "jobs":
        if args.action == "list":
            return client.request(
                "GET", "jobs" + _query(status=args.status, limit=args.limit, offset=args.offset)
            )
        if args.action == "submit":
            return client.request(
                "POST",
                "jobs",
                payload=_read_payload(args.file),
                headers={"Idempotency-Key": args.idempotency_key},
            )
        if args.action == "get":
            return client.request("GET", f"jobs/{args.job_id}")
        if args.action == "cancel":
            return client.request("POST", f"jobs/{args.job_id}/cancel")
        return client.request("GET", f"jobs/{args.job_id}/scheduling-decisions")
    if args.group == "workers":
        if args.action == "register":
            return client.request("POST", "workers/register", payload=_read_payload(args.file))
        worker_path = f"workers/{args.worker_id}"
        headers = _worker_headers(args)
        if args.action in {"heartbeat", "drain", "next-lease", "evict-idle"}:
            endpoint = {
                "heartbeat": "heartbeat",
                "drain": "drain",
                "next-lease": "leases/next",
                "evict-idle": "evict-idle",
            }[args.action]
            return client.request("POST", f"{worker_path}/{endpoint}", headers=headers)
        if args.action == "residencies":
            return client.request("GET", f"{worker_path}/residencies", headers=headers)
        if args.action == "resource-snapshots":
            return client.request("GET", f"{worker_path}/resource-snapshots", headers=headers)
        if args.action == "report-resources":
            return client.request(
                "POST",
                f"{worker_path}/resource-snapshots",
                payload=_read_payload(args.file),
                headers=headers,
            )
        endpoint = {"start": "start", "complete": "complete", "execute": "execute"}[args.action]
        return client.request(
            "POST", f"{worker_path}/attempts/{args.attempt_id}/{endpoint}", headers=headers
        )
    worker_path = f"workers/{args.worker_id}"
    headers = _worker_headers(args)
    if args.action == "run":
        return client.request(
            "POST",
            f"{worker_path}/benchmarks",
            payload=_read_payload(args.file),
            headers=headers,
        )
    return client.request(
        "GET", f"{worker_path}/benchmarks" + _query(limit=args.limit), headers=headers
    )


def run_with_arguments(
    args: argparse.Namespace, client: ApiClient, stdout: Any, stderr: Any
) -> int:
    """Execute parsed arguments; useful in tests because it has no process edges."""

    try:
        response = dispatch(args, client)
    except CliError as error:
        print(f"error: {error}", file=stderr)
        return 1
    if response is None:
        print("No content.", file=stdout)
    else:
        print(json.dumps(response, indent=2, sort_keys=True, default=str), file=stdout)
    return 0


def run(argv: Sequence[str], client: ApiClient, stdout: Any, stderr: Any) -> int:
    """Run one command in a testable form; `main` supplies real process edges."""

    return run_with_arguments(build_parser().parse_args(list(argv)), client, stdout, stderr)


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point installed as `conductor`."""

    arguments = sys.argv[1:] if argv is None else argv
    parsed_arguments = build_parser().parse_args(list(arguments))
    return run_with_arguments(
        parsed_arguments,
        HttpApiClient(parsed_arguments.api_url),
        sys.stdout,
        sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
