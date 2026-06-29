import { apiBaseUrl, authorizedFetch, parseApiErrorMessage } from "./api";

const workflowBase = `${apiBaseUrl}/api/v1/workflows`;

export type WorkflowScheduleType = "once" | "daily" | "interval";
export type WorkflowTaskType = "llm";
export type WorkflowRunStatus = "pending" | "running" | "succeeded" | "failed";

export type WorkflowSummary = {
  id: string;
  name: string;
  description: string | null;
  task_type: WorkflowTaskType;
  prompt: string;
  enabled: boolean;
  schedule_type: WorkflowScheduleType;
  run_at: string | null;
  run_time: string | null;
  interval_minutes: number | null;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowRunSummary = {
  id: string;
  workflow_id: string;
  status: WorkflowRunStatus;
  started_at: string | null;
  finished_at: string | null;
  output_text: string | null;
  error: string | null;
  created_at: string;
};

export type WorkflowDraft = {
  name: string;
  description: string;
  prompt: string;
  enabled: boolean;
  schedule_type: WorkflowScheduleType;
  run_at: string;
  run_time: string;
  interval_minutes: number;
};

function jsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json" };
}

export async function fetchWorkflows(_accessToken?: string | null): Promise<WorkflowSummary[]> {
  const res = await authorizedFetch(workflowBase, { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<WorkflowSummary[]>;
}

export function defaultWorkflowDraft(): WorkflowDraft {
  return {
    name: "",
    description: "",
    prompt: "",
    enabled: true,
    schedule_type: "daily",
    run_at: "",
    run_time: "09:00",
    interval_minutes: 60,
  };
}

export function workflowToDraft(workflow: WorkflowSummary): WorkflowDraft {
  return {
    name: workflow.name,
    description: workflow.description ?? "",
    prompt: workflow.prompt,
    enabled: workflow.enabled,
    schedule_type: workflow.schedule_type,
    run_at: workflow.run_at ? isoToLocalDateTimeInput(workflow.run_at) : "",
    run_time: workflow.run_time ?? "09:00",
    interval_minutes: workflow.interval_minutes ?? 60,
  };
}

export function draftToRequestBody(draft: WorkflowDraft) {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    prompt: draft.prompt.trim(),
    enabled: draft.enabled,
    schedule_type: draft.schedule_type,
    run_at:
      draft.schedule_type === "once" && draft.run_at
        ? localDateTimeInputToIso(draft.run_at)
        : null,
    run_time: draft.schedule_type === "daily" ? draft.run_time : null,
    interval_minutes:
      draft.schedule_type === "interval" ? draft.interval_minutes : null,
  };
}

export function isoToLocalDateTimeInput(iso: string): string {
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function localDateTimeInputToIso(value: string): string {
  return new Date(value).toISOString();
}

export const scheduleTypeLabel: Record<WorkflowScheduleType, string> = {
  once: "Once",
  daily: "Daily",
  interval: "Every N minutes",
};

export const runStatusLabel: Record<WorkflowRunStatus, string> = {
  pending: "Pending",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
};

export async function createWorkflow(
  _accessToken: string | null | undefined,
  body: ReturnType<typeof draftToRequestBody>,
): Promise<WorkflowSummary> {
  const res = await authorizedFetch(workflowBase, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<WorkflowSummary>;
}

export async function updateWorkflow(
  _accessToken: string | null | undefined,
  workflowId: string,
  body: Partial<ReturnType<typeof draftToRequestBody>>,
): Promise<WorkflowSummary> {
  const res = await authorizedFetch(`${workflowBase}/${encodeURIComponent(workflowId)}`, {
    method: "PATCH",
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<WorkflowSummary>;
}

export async function deleteWorkflow(
  _accessToken: string | null | undefined,
  workflowId: string,
): Promise<void> {
  const res = await authorizedFetch(`${workflowBase}/${encodeURIComponent(workflowId)}`, {
    method: "DELETE",
    headers: jsonHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
}

export async function fetchWorkflowRuns(
  _accessToken: string | null | undefined,
  workflowId: string,
): Promise<WorkflowRunSummary[]> {
  const res = await authorizedFetch(
    `${workflowBase}/${encodeURIComponent(workflowId)}/runs`,
    { method: "GET" },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<WorkflowRunSummary[]>;
}

export async function triggerWorkflowRun(
  _accessToken: string | null | undefined,
  workflowId: string,
): Promise<WorkflowRunSummary> {
  const res = await authorizedFetch(
    `${workflowBase}/${encodeURIComponent(workflowId)}/run`,
    { method: "POST", headers: jsonHeaders() },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  const data = (await res.json()) as { run: WorkflowRunSummary };
  return data.run;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
