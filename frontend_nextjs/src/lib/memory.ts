import { apiBaseUrl, authorizedFetch, parseApiErrorMessage } from "./api";

const memoryBase = `${apiBaseUrl}/api/v1/memory`;

export type MemoryCategory = "fact" | "preference" | "profile" | "goal" | "other";
export type MemorySource = "agent" | "user" | "system";

export type UserMemory = {
  id: string;
  category: MemoryCategory;
  content: string;
  source: MemorySource;
  conversation_id: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateMemoryRequest = {
  category?: MemoryCategory;
  content: string;
};

function jsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json" };
}

export async function fetchMemories(_accessToken?: string | null): Promise<UserMemory[]> {
  const res = await authorizedFetch(`${memoryBase}`, { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<UserMemory[]>;
}

export async function createMemory(
  _accessToken: string | null | undefined,
  body: CreateMemoryRequest,
): Promise<UserMemory> {
  const res = await authorizedFetch(`${memoryBase}`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<UserMemory>;
}

export async function deleteMemory(
  _accessToken: string | null | undefined,
  memoryId: string,
): Promise<void> {
  const res = await authorizedFetch(`${memoryBase}/${encodeURIComponent(memoryId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
}

export const memoryCategoryLabel: Record<MemoryCategory, string> = {
  fact: "Fact",
  preference: "Preference",
  profile: "Profile",
  goal: "Goal",
  other: "Note",
};
