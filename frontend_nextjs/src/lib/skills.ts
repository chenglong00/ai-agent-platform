import { apiBaseUrl, parseApiErrorMessage } from "./api";
import {
  defaultDocumentAccess,
  visibilityLabel,
  type AccessVisibilityOption,
  type DocumentAccessControl,
  type GroupOption,
  type RoleOption,
  type Visibility,
} from "./knowledge-base";

const skillsBase = `${apiBaseUrl}/api/v1/skills`;

export type SkillSource = "builtin" | "custom";
export type SkillAccessControl = DocumentAccessControl;

export type SkillOptions = {
  access_visibility_options: AccessVisibilityOption[];
  role_options: RoleOption[];
  groups: GroupOption[];
};

export type SkillSummary = {
  id: string;
  slug: string;
  name: string;
  description: string;
  source: SkillSource;
  enabled: boolean;
  access: SkillAccessControl;
  is_owner: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type SkillDetail = SkillSummary & {
  content: string;
  can_manage: boolean;
};

export type CreateSkillRequest = {
  name: string;
  description?: string;
  content: string;
  slug?: string;
  enabled?: boolean;
  access?: SkillAccessControl;
};

export type UpdateSkillRequest = Partial<CreateSkillRequest>;

function authHeaders(accessToken: string, json = true): HeadersInit {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken.trim()}`,
  };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

export async function fetchSkillOptions(
  accessToken: string,
): Promise<SkillOptions> {
  const res = await fetch(`${skillsBase}/options`, {
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillOptions>;
}

export async function fetchBuiltinSkills(
  accessToken: string,
): Promise<SkillSummary[]> {
  const res = await fetch(`${skillsBase}/builtins`, {
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillSummary[]>;
}

export async function fetchBuiltinSkill(
  accessToken: string,
  slug: string,
): Promise<SkillDetail> {
  const res = await fetch(`${skillsBase}/builtins/${encodeURIComponent(slug)}`, {
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillDetail>;
}

export function formatAgentSkillView(
  name: string,
  description: string,
  content: string,
): string {
  const header = description.trim()
    ? `# ${name}\n\n${description.trim()}\n\n`
    : `# ${name}\n\n`;
  return header + content.trim();
}

export async function fetchSkills(
  accessToken: string,
): Promise<SkillSummary[]> {
  const res = await fetch(`${skillsBase}`, {
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillSummary[]>;
}

export async function fetchSkill(
  accessToken: string,
  skillId: string,
): Promise<SkillDetail> {
  const res = await fetch(`${skillsBase}/${encodeURIComponent(skillId)}`, {
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillDetail>;
}

export async function createSkill(
  accessToken: string,
  body: CreateSkillRequest,
): Promise<SkillDetail> {
  const res = await fetch(`${skillsBase}`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillDetail>;
}

export async function updateSkill(
  accessToken: string,
  skillId: string,
  body: UpdateSkillRequest,
): Promise<SkillDetail> {
  const res = await fetch(`${skillsBase}/${encodeURIComponent(skillId)}`, {
    method: "PATCH",
    headers: authHeaders(accessToken),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillDetail>;
}

export async function deleteSkill(
  accessToken: string,
  skillId: string,
): Promise<{ id: string; deleted: boolean }> {
  const res = await fetch(`${skillsBase}/${encodeURIComponent(skillId)}`, {
    method: "DELETE",
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<{ id: string; deleted: boolean }>;
}

export { defaultDocumentAccess as defaultSkillAccess, visibilityLabel };

export const defaultSkillDraft = (): CreateSkillRequest => ({
  name: "",
  description: "",
  content: "",
  enabled: true,
  access: defaultDocumentAccess(),
});

export type { Visibility };
