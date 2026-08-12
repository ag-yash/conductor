import type {
  Benchmark,
  Health,
  JobPage,
  Model,
  Residency,
  SchedulingDecision,
  Worker,
} from "./types";

const apiBaseUrl = import.meta.env.VITE_CONDUCTOR_API_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string, headers?: HeadersInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json", ...headers },
  });
  if (!response.ok) {
    throw new ApiError(`Conductor returned HTTP ${response.status} for ${path}.`);
  }
  return (await response.json()) as T;
}

export const api = {
  ready: () => getJson<Health>("/health/ready"),
  jobs: (options: { status?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams({
      limit: String(options.limit ?? 8),
      offset: String(options.offset ?? 0),
    });
    if (options.status !== undefined) query.set("status", options.status);
    return getJson<JobPage>(`/jobs?${query.toString()}`);
  },
  models: () => getJson<Model[]>("/models"),
  workers: () => getJson<Worker[]>("/workers"),
  schedulingDecisions: (jobId: string) =>
    getJson<SchedulingDecision[]>(`/jobs/${encodeURIComponent(jobId)}/scheduling-decisions`),
  residencies: (worker: Worker) =>
    getJson<Residency[]>(
      `/workers/${encodeURIComponent(worker.id)}/residencies`,
      { "Worker-Instance-ID": worker.instance_id },
    ),
  benchmarks: (worker: Worker) =>
    getJson<Benchmark[]>(
      `/workers/${encodeURIComponent(worker.id)}/benchmarks?limit=5`,
      { "Worker-Instance-ID": worker.instance_id },
    ),
};
