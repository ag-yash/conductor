# Workers

Owns the worker protocol: registration, process-instance IDs, heartbeats,
resource reports, polling, and draining. `runner.py` is the standalone
`conductor-worker` executable. It measures its own host/process resources with
`psutil` and drives the existing worker HTTP contract. A process-instance ID is
the plain-English name for the distributed-systems term “epoch.”
