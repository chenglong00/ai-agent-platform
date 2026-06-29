import { apiBaseUrl, authorizedFetch, parseApiErrorMessage } from "./api";

const subagentBase = `${apiBaseUrl}/api/v1/subagents`;

export type SubagentSkillSummary = {
  id: string;
  name: string;
  description: string;
  tags: string[];
};

export type SubagentSummary = {
  id: string;
  name: string;
  description: string;
  agent_url: string;
  enabled: boolean;
  agent_version: string | null;
  streaming: boolean;
  skills: SubagentSkillSummary[];
  last_verified_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type RegisterSubagentRequest = {
  agent_url: string;
  name?: string;
  description?: string;
};

export type UpdateSubagentRequest = {
  enabled?: boolean;
  name?: string;
  description?: string;
};

function jsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json" };
}

export async function fetchSubagents(
  _accessToken?: string | null,
): Promise<SubagentSummary[]> {
  const res = await authorizedFetch(subagentBase, { method: "GET" });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return res.json();
}

export async function registerSubagent(
  _accessToken: string | null | undefined,
  body: RegisterSubagentRequest,
): Promise<SubagentSummary> {
  const res = await authorizedFetch(`${subagentBase}/register`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return res.json();
}

export async function refreshSubagent(
  _accessToken: string | null | undefined,
  subagentId: string,
): Promise<SubagentSummary> {
  const res = await authorizedFetch(
    `${subagentBase}/${encodeURIComponent(subagentId)}/refresh`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  const payload = (await res.json()) as { subagent: SubagentSummary };
  return payload.subagent;
}

export async function updateSubagent(
  _accessToken: string | null | undefined,
  subagentId: string,
  body: UpdateSubagentRequest,
): Promise<SubagentSummary> {
  const res = await authorizedFetch(
    `${subagentBase}/${encodeURIComponent(subagentId)}`,
    {
      method: "PATCH",
      headers: jsonHeaders(),
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return res.json();
}

export async function deleteSubagent(
  _accessToken: string | null | undefined,
  subagentId: string,
): Promise<void> {
  const res = await authorizedFetch(
    `${subagentBase}/${encodeURIComponent(subagentId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
