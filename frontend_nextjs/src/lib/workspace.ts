import { apiBaseUrl, authorizedFetch, parseApiErrorMessage } from "./api";

const workspaceBase = `${apiBaseUrl}/api/v1/workspace`;

export type WorkspaceEntry = {
  name: string;
  /** Workspace-relative POSIX path (no leading slash). */
  path: string;
  type: "file" | "directory";
  size: number;
  modified_at: number | null;
};

export type WorkspaceTreeResult = {
  root: string;
  entries: WorkspaceEntry[];
};

export type WorkspaceRootResult = {
  root: string;
  backend: string;
};

export type WorkspaceFileResult = {
  path: string;
  size: number;
  modified_at: number | null;
  content: string;
  truncated: boolean;
  binary: boolean;
};

export async function fetchWorkspaceRoot(
  _accessToken?: string | null,
): Promise<WorkspaceRootResult> {
  const res = await authorizedFetch(`${workspaceBase}/root`, { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return (await res.json()) as WorkspaceRootResult;
}

export async function fetchWorkspaceTree(
  _accessToken: string | null | undefined,
  path = "",
): Promise<WorkspaceTreeResult> {
  const url = new URL(`${workspaceBase}/tree`, window.location.origin);
  if (path) url.searchParams.set("path", path);
  const res = await authorizedFetch(url.toString(), { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return (await res.json()) as WorkspaceTreeResult;
}

export async function fetchWorkspaceFile(
  _accessToken: string | null | undefined,
  path: string,
): Promise<WorkspaceFileResult> {
  const url = new URL(`${workspaceBase}/file`, window.location.origin);
  url.searchParams.set("path", path);
  const res = await authorizedFetch(url.toString(), { method: "GET" });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return (await res.json()) as WorkspaceFileResult;
}

/** Tree node used by the file explorer (UI shape, not API shape). */
export type WorkspaceTreeNode = WorkspaceEntry & {
  children?: WorkspaceTreeNode[];
};

/** Convert flat entry list (sorted dirs-first) into a nested tree. */
export function buildWorkspaceTree(entries: WorkspaceEntry[]): WorkspaceTreeNode[] {
  const nodes = new Map<string, WorkspaceTreeNode>();
  const root: WorkspaceTreeNode[] = [];

  for (const entry of entries) {
    const node: WorkspaceTreeNode = {
      ...entry,
      children: entry.type === "directory" ? [] : undefined,
    };
    nodes.set(entry.path, node);
  }

  for (const entry of entries) {
    const node = nodes.get(entry.path)!;
    const slash = entry.path.lastIndexOf("/");
    if (slash === -1) {
      root.push(node);
    } else {
      const parent = nodes.get(entry.path.slice(0, slash));
      if (parent && parent.children) parent.children.push(node);
      else root.push(node);
    }
  }

  const sortNodes = (list: WorkspaceTreeNode[]) => {
    list.sort((a, b) => {
      if (a.type !== b.type) return a.type === "directory" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const n of list) if (n.children) sortNodes(n.children);
  };
  sortNodes(root);

  return root;
}
