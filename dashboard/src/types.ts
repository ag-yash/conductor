export type Health = {
  status: "ready" | "not_ready";
  checks: Record<string, "ready" | "not_ready">;
};

export type Job = {
  id: string;
  task: string;
  model_id: string;
  status: string;
  priority: string;
  created_at: string;
};

export type JobPage = { items: Job[]; limit: number; offset: number };

export type Model = {
  id: string;
  display_name: string;
  runtime_kind: string;
  supported_tasks: string[];
  enabled: boolean;
};

export type Worker = {
  id: string;
  instance_id: string;
  supported_tasks: string[];
  max_parallel_jobs: number;
  status: string;
  last_heartbeat_at: string;
};
