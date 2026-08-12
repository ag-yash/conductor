import { useCallback, useEffect, useState, type ReactNode } from "react";

import { api } from "./api";
import { QueueExplorer } from "./QueueExplorer";
import type {
  Benchmark,
  Health,
  Job,
  Model,
  Residency,
  SchedulingDecision,
  Worker,
} from "./types";

type DashboardState = {
  health: Health | null;
  jobs: Job[];
  models: Model[];
  workers: Worker[];
};

const emptyState: DashboardState = { health: null, jobs: [], models: [], workers: [] };

function formatTime(value: string | null): string {
  if (value === null) return "Not recorded";
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function formatJson(value: Record<string, unknown> | null): string {
  return JSON.stringify(value, null, 2);
}

function statusTone(value: string): "good" | "warn" | "neutral" {
  if (["ready", "succeeded", "enabled"].includes(value)) return "good";
  if (["failed", "draining", "not_ready", "disabled"].includes(value)) return "warn";
  return "neutral";
}

export function App() {
  const [state, setState] = useState<DashboardState>(emptyState);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [selectedWorker, setSelectedWorker] = useState<Worker | null>(null);
  const [decisions, setDecisions] = useState<SchedulingDecision[] | null>(null);
  const [residencies, setResidencies] = useState<Residency[] | null>(null);
  const [benchmarks, setBenchmarks] = useState<Benchmark[] | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

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

  useEffect(() => {
    if (selectedJob === null) return;
    let isCurrent = true;
    setDecisions(null);
    setDetailError(null);
    void api
      .schedulingDecisions(selectedJob.id)
      .then((items) => {
        if (isCurrent) setDecisions(items);
      })
      .catch((reason: unknown) => {
        if (isCurrent) setDetailError(readableError(reason));
      });
    return () => {
      isCurrent = false;
    };
  }, [selectedJob]);

  useEffect(() => {
    if (selectedWorker === null) return;
    let isCurrent = true;
    setResidencies(null);
    setBenchmarks(null);
    setDetailError(null);
    void Promise.all([api.residencies(selectedWorker), api.benchmarks(selectedWorker)])
      .then(([nextResidencies, nextBenchmarks]) => {
        if (!isCurrent) return;
        setResidencies(nextResidencies);
        setBenchmarks(nextBenchmarks);
      })
      .catch((reason: unknown) => {
        if (isCurrent) setDetailError(readableError(reason));
      });
    return () => {
      isCurrent = false;
    };
  }, [selectedWorker]);

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
            Select a job or worker to inspect the durable facts behind the overview: its
            scheduler decision, result, model residency, and benchmark history.
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
          <PanelHeading title="Recent jobs" subtitle="Select a job to inspect its outcome and saved placement rationale." />
          {state.jobs.length === 0 ? (
            <EmptyState message="No jobs yet. Submit one with the CLI to see it here." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Task</th><th>Model</th><th>Priority</th><th>Status</th><th>Created</th></tr></thead>
                <tbody>{state.jobs.map((job) => <tr key={job.id} className={selectedJob?.id === job.id ? "selected-row" : ""}>
                  <td><button className="table-action" onClick={() => setSelectedJob(job)}><strong>{job.task}</strong><span className="secondary">{job.id.slice(0, 8)}</span></button></td>
                  <td>{job.model_id}</td><td>{job.priority}</td>
                  <td><Badge value={job.status} /></td><td>{formatTime(job.created_at)}</td>
                </tr>)}</tbody>
              </table>
            </div>
          )}
        </article>

        <article className="panel">
          <PanelHeading title="Workers" subtitle="Select a worker to inspect its loaded-model snapshot and benchmark history." />
          <div className="stack">
            {state.workers.length === 0 ? <EmptyState message="No worker has registered." /> : state.workers.map((worker) => (
              <button className={`worker interactive ${selectedWorker?.id === worker.id ? "selected-card" : ""}`} key={worker.id} onClick={() => setSelectedWorker(worker)}>
                <div><strong>{worker.id}</strong><span className="secondary">{worker.instance_id}</span></div>
                <Badge value={worker.status} />
                <span className="slot-count">{worker.max_parallel_jobs} slot{worker.max_parallel_jobs === 1 ? "" : "s"}</span>
              </button>
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

      <QueueExplorer selectedJobId={selectedJob?.id ?? null} onSelectJob={setSelectedJob} />

      {selectedJob || selectedWorker ? <section className="detail-grid" aria-label="Selected investigation details">
        {selectedJob ? <JobDetail job={selectedJob} decisions={decisions} error={detailError} onClose={() => setSelectedJob(null)} /> : null}
        {selectedWorker ? <WorkerDetail worker={selectedWorker} residencies={residencies} benchmarks={benchmarks} error={detailError} onClose={() => setSelectedWorker(null)} /> : null}
      </section> : null}
    </main>
  );
}

function JobDetail({ job, decisions, error, onClose }: { job: Job; decisions: SchedulingDecision[] | null; error: string | null; onClose: () => void }) {
  return <article className="panel detail-panel"><DetailHeading title={`Job: ${job.task}`} onClose={onClose} />
    <div className="detail-summary"><Badge value={job.status} /><span className="secondary">Updated {formatTime(job.updated_at)}</span></div>
    <DetailBlock title="Result"><CodeBlock value={job.result} empty="This job has not produced a result yet." /></DetailBlock>
    {job.error_message ? <DetailBlock title="Runtime error"><p className="detail-error">{job.error_message}</p></DetailBlock> : null}
    <DetailBlock title="Scheduling rationale"><p className="hint">This is the immutable record of why Conductor selected or deferred a worker when it evaluated this job.</p>{error ? <p className="detail-error">{error}</p> : decisions === null ? <p className="empty">Loading saved decisions…</p> : decisions.length === 0 ? <EmptyState message="No scheduling decision has been recorded yet." /> : decisions.map((decision) => <div className="decision" key={decision.id}><strong>{decision.outcome.replaceAll("_", " ")}</strong><span className="secondary">{decision.reason}</span>{decision.candidates.map((candidate) => <div className="candidate" key={candidate.worker_id}><Badge value={candidate.eligible ? "eligible" : "ineligible"} /><span><strong>{candidate.worker_id}</strong> — {candidate.reason}</span><span className="slot-count">{candidate.active_slots}/{candidate.max_parallel_jobs} slots</span></div>)}</div>)}</DetailBlock>
  </article>;
}

function WorkerDetail({ worker, residencies, benchmarks, error, onClose }: { worker: Worker; residencies: Residency[] | null; benchmarks: Benchmark[] | null; error: string | null; onClose: () => void }) {
  return <article className="panel detail-panel"><DetailHeading title={`Worker: ${worker.id}`} onClose={onClose} />
    <p className="secondary">Current process instance: {worker.instance_id}. A restart changes this ID, so old process messages cannot update new worker state.</p>
    {error ? <p className="detail-error">{error}</p> : <>
      <DetailBlock title="Model residency"><p className="hint">A residency means a specific worker process has loaded a model. It is different from merely registering a model definition.</p>{residencies === null ? <p className="empty">Loading residency snapshots…</p> : residencies.length === 0 ? <EmptyState message="No model is currently recorded as resident on this worker." /> : residencies.map((residency) => <div className="residency" key={residency.id}><div><strong>{residency.model_id}</strong><span className="secondary">Last used {formatTime(residency.last_used_at)} · {residency.active_execution_count} active executions</span></div><Badge value={residency.status} /></div>)}</DetailBlock>
      <DetailBlock title="Recent benchmarks"><p className="hint">These are warm-runtime execution measurements, not model-quality scores.</p>{benchmarks === null ? <p className="empty">Loading benchmark history…</p> : benchmarks.length === 0 ? <EmptyState message="No benchmark has been recorded for this worker process." /> : benchmarks.map((benchmark) => <div className="benchmark" key={benchmark.id}><div><strong>{benchmark.model_id} · {benchmark.task}</strong><span className="secondary">{benchmark.measurement_iterations} measured runs after {benchmark.warmup_iterations} warmups</span></div><strong>{benchmark.mean_wall_time_ms.toFixed(3)} ms mean</strong></div>)}</DetailBlock>
    </>}
  </article>;
}

function DetailHeading({ title, onClose }: { title: string; onClose: () => void }) { return <header className="detail-heading"><h3>{title}</h3><button className="close-button" onClick={onClose}>Close</button></header>; }
function DetailBlock({ title, children }: { title: string; children: ReactNode }) { return <section className="detail-block"><h4>{title}</h4>{children}</section>; }
function CodeBlock({ value, empty }: { value: Record<string, unknown> | null; empty: string }) { return value === null ? <EmptyState message={empty} /> : <pre>{formatJson(value)}</pre>; }
function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "good" | "warn" | "neutral" }) { return <article className="metric"><p>{label}</p><strong className={tone}>{value}</strong></article>; }
function PanelHeading({ title, subtitle }: { title: string; subtitle: string }) { return <header className="panel-heading"><h3>{title}</h3><p>{subtitle}</p></header>; }
function Badge({ value }: { value: string }) { return <span className={`badge ${statusTone(value)}`}>{value.replaceAll("_", " ")}</span>; }
function EmptyState({ message }: { message: string }) { return <p className="empty">{message}</p>; }
function readableError(reason: unknown): string { return reason instanceof Error ? reason.message : "Could not load this detail."; }
