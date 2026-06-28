import { apiBaseUrl, parseApiErrorMessage } from "./api";

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

function authHeaders(accessToken: string): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken.trim()}`,
    "Content-Type": "application/json",
  };
}

export async function fetchMemories(accessToken: string): Promise<UserMemory[]> {
  const res = await fetch(`${memoryBase}`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<UserMemory[]>;
}

export async function createMemory(
  accessToken: string,
  body: CreateMemoryRequest,
): Promise<UserMemory> {
  const res = await fetch(`${memoryBase}`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<UserMemory>;
}

export async function deleteMemory(
  accessToken: string,
  memoryId: string,
): Promise<void> {
  const res = await fetch(`${memoryBase}/${encodeURIComponent(memoryId)}`, {
    method: "DELETE",
    headers: authHeaders(accessToken),
    cache: "no-store",
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
