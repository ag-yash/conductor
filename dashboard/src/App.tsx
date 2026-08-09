import { useCallback, useEffect, useState } from "react";

import { api } from "./api";
import type { Health, Job, Model, Worker } from "./types";

type DashboardState = {
  health: Health | null;
  jobs: Job[];
  models: Model[];
  workers: Worker[];
};

const emptyState: DashboardState = { health: null, jobs: [], models: [], workers: [] };

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function statusTone(value: string): "good" | "warn" | "neutral" {
  if (["ready", "succeeded"].includes(value)) return "good";
  if (["failed", "draining", "not_ready"].includes(value)) return "warn";
  return "neutral";
}

export function App() {
  const [state, setState] = useState<DashboardState>(emptyState);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // These reads are independent. Fetching them together makes the overview
      // feel responsive without changing any control-plane state.
      const [health, jobPage, models, workers] = await Promise.all([
        api.ready(),
        api.jobs(),
        api.models(),
        api.workers(),
      ]);
      setState({ health, jobs: jobPage.items, models, workers });
      setLastUpdated(new Date());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load Conductor.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const ready = state.health?.status === "ready";
  const activeJobs = state.jobs.filter((job) => ["assigned", "running"].includes(job.status));

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">C</span>
          <div>
            <p className="eyebrow">LOCAL AI CONTROL PLANE</p>
            <h1>Conductor</h1>
          </div>
        </div>
        <div className="topbar-actions">
          <span className={`connection ${ready ? "connected" : "disconnected"}`}>
            <i /> {ready ? "Control plane ready" : "Control plane unavailable"}
          </span>
          <button onClick={() => void refresh()} disabled={isLoading}>
            {isLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">OVERVIEW</p>
          <h2>Your local AI workloads, explained.</h2>
          <p className="hero-copy">
            This is a read-only view of the same API used by the CLI. It does not invent
            state or make scheduling decisions in the browser.
          </p>
        </div>
        <p className="last-updated">
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Waiting for API…"}
        </p>
      </section>

      {error ? <section className="error-banner">{error}</section> : null}

      <section className="metrics" aria-label="Control plane summary">
        <Metric label="Control plane" value={ready ? "Ready" : "Unknown"} tone={ready ? "good" : "warn"} />
        <Metric label="Registered workers" value={String(state.workers.length)} />
        <Metric label="Active jobs" value={String(activeJobs.length)} />
        <Metric label="Trusted models" value={String(state.models.length)} />
      </section>

      <section className="grid">
        <article className="panel wide">
          <PanelHeading title="Recent jobs" subtitle="The latest durable work accepted by Conductor." />
          {state.jobs.length === 0 ? (
            <EmptyState message="No jobs yet. Submit one with the CLI to see it here." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Task</th><th>Model</th><th>Priority</th><th>Status</th><th>Created</th></tr></thead>
                <tbody>{state.jobs.map((job) => <tr key={job.id}>
                  <td><strong>{job.task}</strong><span className="secondary">{job.id.slice(0, 8)}</span></td>
                  <td>{job.model_id}</td><td>{job.priority}</td>
                  <td><Badge value={job.status} /></td><td>{formatTime(job.created_at)}</td>
                </tr>)}</tbody>
              </table>
            </div>
          )}
        </article>

        <article className="panel">
          <PanelHeading title="Workers" subtitle="Current process instances that can lease work." />
          <div className="stack">
            {state.workers.length === 0 ? <EmptyState message="No worker has registered." /> : state.workers.map((worker) => (
              <div className="worker" key={worker.id}>
                <div><strong>{worker.id}</strong><span className="secondary">{worker.instance_id}</span></div>
                <Badge value={worker.status} />
                <span className="slot-count">{worker.max_parallel_jobs} slot{worker.max_parallel_jobs === 1 ? "" : "s"}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <PanelHeading title="Models" subtitle="Trusted definitions available to workers." />
          <div className="stack">
            {state.models.length === 0 ? <EmptyState message="No model definition has been registered." /> : state.models.map((model) => (
              <div className="model" key={model.id}>
                <div><strong>{model.display_name}</strong><span className="secondary">{model.id} · {model.runtime_kind}</span></div>
                <Badge value={model.enabled ? "enabled" : "disabled"} />
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "good" | "warn" | "neutral" }) {
  return <article className="metric"><p>{label}</p><strong className={tone}>{value}</strong></article>;
}

function PanelHeading({ title, subtitle }: { title: string; subtitle: string }) {
  return <header className="panel-heading"><h3>{title}</h3><p>{subtitle}</p></header>;
}

function Badge({ value }: { value: string }) {
  return <span className={`badge ${statusTone(value)}`}>{value.replaceAll("_", " ")}</span>;
}

function EmptyState({ message }: { message: string }) {
  return <p className="empty">{message}</p>;
}
