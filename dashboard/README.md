# Dashboard

This is Conductor's React and TypeScript operator interface. Its first screen
is intentionally read-only: it shows the control-plane readiness, recent jobs,
registered workers, and trusted model definitions by calling the same versioned
HTTP API used by the CLI.

The browser never reads SQLite or re-implements scheduler rules. It is a thin
view over the control plane, which means the CLI and dashboard cannot disagree
about what Conductor currently knows.

## Run it locally

In one terminal, start the backend from the repository root:

```bash
conductor-api
```

In another terminal:

```bash
cd dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite forwards browser requests beginning with
`/api` to the local FastAPI server at `127.0.0.1:8080`, so no CORS setup is
needed during development.

Use `npm run build` to type-check and produce a production frontend bundle.
