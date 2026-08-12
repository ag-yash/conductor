import type { Health, JobPage, Model, Worker } from "./types";

const apiBaseUrl = import.meta.env.VITE_CONDUCTOR_API_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiError(`Conductor returned HTTP ${response.status} for ${path}.`);
  }
  return (await response.json()) as T;
}

export const api = {
  ready: () => getJson<Health>("/health/ready"),
  jobs: () => getJson<JobPage>("/jobs?limit=8&offset=0"),
  models: () => getJson<Model[]>("/models"),
  workers: () => getJson<Worker[]>("/workers"),
};
