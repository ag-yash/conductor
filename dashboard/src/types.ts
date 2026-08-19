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
  input: Record<string, unknown>;
  parameters: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error_message: string | null;
  updated_at: string;
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

export type SchedulingCandidate = {
  worker_id: string;
  eligible: boolean;
  reason: string;
  active_slots: number;
  max_parallel_jobs: number;
  available_memory_bytes: number | null;
  required_memory_bytes: number | null;
};

export type SchedulingDecision = {
  id: string;
  selected_worker_id: string | null;
  outcome: string;
  reason: string;
  candidates: SchedulingCandidate[];
  created_at: string;
};

export type Residency = {
  id: string;
  model_id: string;
  model_revision: number;
  status: string;
  active_execution_count: number;
  measured_memory_bytes: number | null;
  loaded_at: string | null;
  last_used_at: string | null;
  failure_message: string | null;
};

export type Benchmark = {
  id: string;
  model_id: string;
  task: string;
  warmup_iterations: number;
  measurement_iterations: number;
  mean_wall_time_ms: number;
  min_wall_time_ms: number;
  max_wall_time_ms: number;
  mean_runtime_metrics: Record<string, number>;
  created_at: string;
};

export type ResourceSnapshot = {
  id: string;
  worker_id: string;
  worker_instance_id: string;
  host_cpu_percent: number;
  host_total_memory_bytes: number;
  host_available_memory_bytes: number;
  process_cpu_percent: number;
  process_memory_bytes: number;
  observed_at: string;
};
