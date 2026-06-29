import { apiBaseUrl, authorizedFetch, parseApiErrorMessage } from "./api";
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

function jsonHeaders(includeBody = true): HeadersInit {
  return includeBody ? { "Content-Type": "application/json" } : {};
}

export async function fetchSkillOptions(
  _accessToken?: string | null,
): Promise<SkillOptions> {
  const res = await authorizedFetch(`${skillsBase}/options`, { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillOptions>;
}

export async function fetchBuiltinSkills(
  _accessToken?: string | null,
): Promise<SkillSummary[]> {
  const res = await authorizedFetch(`${skillsBase}/builtins`, { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillSummary[]>;
}

export async function fetchBuiltinSkill(
  _accessToken: string | null | undefined,
  slug: string,
): Promise<SkillDetail> {
  const res = await authorizedFetch(`${skillsBase}/builtins/${encodeURIComponent(slug)}`, {
    method: "GET",
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
  _accessToken?: string | null,
): Promise<SkillSummary[]> {
  const res = await authorizedFetch(`${skillsBase}`, { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillSummary[]>;
}

/** Built-in skills plus enabled custom skills (for slash-command autocomplete). */
export async function fetchAllAvailableSkills(
  accessToken?: string | null,
): Promise<SkillSummary[]> {
  const [builtins, custom] = await Promise.all([
    fetchBuiltinSkills(accessToken),
    fetchSkills(accessToken),
  ]);
  return [...builtins, ...custom.filter(skill => skill.enabled)];
}

export async function fetchSkill(
  _accessToken: string | null | undefined,
  skillId: string,
): Promise<SkillDetail> {
  const res = await authorizedFetch(`${skillsBase}/${encodeURIComponent(skillId)}`, {
    method: "GET",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillDetail>;
}

export async function createSkill(
  _accessToken: string | null | undefined,
  body: CreateSkillRequest,
): Promise<SkillDetail> {
  const res = await authorizedFetch(`${skillsBase}`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillDetail>;
}

export async function updateSkill(
  _accessToken: string | null | undefined,
  skillId: string,
  body: UpdateSkillRequest,
): Promise<SkillDetail> {
  const res = await authorizedFetch(`${skillsBase}/${encodeURIComponent(skillId)}`, {
    method: "PATCH",
    headers: jsonHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<SkillDetail>;
}

export async function deleteSkill(
  _accessToken: string | null | undefined,
  skillId: string,
): Promise<{ id: string; deleted: boolean }> {
  const res = await authorizedFetch(`${skillsBase}/${encodeURIComponent(skillId)}`, {
    method: "DELETE",
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
