# Docker

This folder contains the container build definitions used by the root
[`docker-compose.yml`](../docker-compose.yml) file.

- `api.Dockerfile` packages the Python control plane and the separate worker
  executable in one image.
- `dashboard.Dockerfile` builds the React dashboard, then serves its static
  files with Nginx.
- `dashboard.nginx.conf` forwards browser `/api/...` calls to the API container
  so the dashboard stays same-origin and does not need a CORS exception.

Read [`docs/docker.md`](../docs/docker.md) before running Compose. It explains
the topology, the fixture-model demo, what data persists, and why the worker is
its own container.
