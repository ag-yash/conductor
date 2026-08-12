import { useEffect, useState } from "react";

import { api } from "./api";
import type { Job } from "./types";

const pageSize = 10;
const fetchSize = pageSize + 1;
const statuses = ["all", "queued", "assigned", "running", "succeeded", "failed", "cancelled"] as const;
type QueueStatus = (typeof statuses)[number];

type Props = {
  selectedJobId: string | null;
  onSelectJob: (job: Job) => void;
};

/**
 * A separate explorer avoids making the overview request unbounded. It asks
 * SQLite for one page at a time, just like a real operator UI would at scale.
 */
export function QueueExplorer({ selectedJobId, onSelectJob }: Props) {
  const [status, setStatus] = useState<QueueStatus>("all");
  const [offset, setOffset] = useState(0);
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isCurrent = true;
    setJobs(null);
    setError(null);
    void api
      // Fetch one additional row. The current API intentionally returns a page,
      // not an expensive total count; this extra row tells us whether Next is real.
      .jobs({ status: status === "all" ? undefined : status, limit: fetchSize, offset })
      .then((page) => {
        if (isCurrent) setJobs(page.items);
      })
      .catch((reason: unknown) => {
        if (isCurrent) setError(reason instanceof Error ? reason.message : "Could not load jobs.");
      });
    return () => {
      isCurrent = false;
    };
  }, [offset, status]);

  function chooseStatus(nextStatus: QueueStatus): void {
    // The old page offset belongs to a different result set after a filter
    // changes. Resetting prevents an apparently empty page from confusing an operator.
    setStatus(nextStatus);
    setOffset(0);
  }

  const visibleJobs = jobs?.slice(0, pageSize) ?? null;
  const hasNextPage = jobs !== null && jobs.length > pageSize;
  const rangeStart = visibleJobs === null || visibleJobs.length === 0 ? 0 : offset + 1;
  const rangeEnd = offset + (visibleJobs?.length ?? 0);

  return <article className="panel queue-panel">
    <header className="queue-heading">
      <div><h3>Queue explorer</h3><p>Filter durable jobs; select any row to inspect its result and placement record.</p></div>
      <span className="queue-range">{jobs === null ? "Loading…" : `Showing ${rangeStart}–${rangeEnd}`}</span>
    </header>
    <div className="filter-bar" aria-label="Job status filter">
      {statuses.map((item) => <button className={`filter-button ${status === item ? "active-filter" : ""}`} key={item} onClick={() => chooseStatus(item)}>{item}</button>)}
    </div>
    {error ? <p className="detail-error">{error}</p> : visibleJobs === null ? <p className="empty">Loading queue page…</p> : visibleJobs.length === 0 ? <p className="empty">No {status === "all" ? "jobs" : `${status} jobs`} at this page.</p> : <div className="table-wrap"><table>
      <thead><tr><th>Task</th><th>Model</th><th>Status</th><th>Updated</th></tr></thead>
      <tbody>{visibleJobs.map((job) => <tr className={selectedJobId === job.id ? "selected-row" : ""} key={job.id}>
        <td><button className="table-action" onClick={() => onSelectJob(job)}><strong>{job.task}</strong><span className="secondary">{job.id.slice(0, 8)}</span></button></td>
        <td>{job.model_id}</td><td><span className={`badge ${statusTone(job.status)}`}>{job.status}</span></td><td>{formatTime(job.updated_at)}</td>
      </tr>)}</tbody>
    </table></div>}
    <footer className="pagination"><button disabled={offset === 0 || jobs === null} onClick={() => setOffset((current) => Math.max(0, current - pageSize))}>Previous</button><button disabled={!hasNextPage || jobs === null} onClick={() => setOffset((current) => current + pageSize)}>Next</button></footer>
  </article>;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value));
}

function statusTone(value: string): "good" | "warn" | "neutral" {
  if (["ready", "succeeded", "enabled"].includes(value)) return "good";
  if (["failed", "draining", "not_ready", "disabled"].includes(value)) return "warn";
  return "neutral";
}
