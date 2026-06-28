import { fetchKnowledgeBaseDocuments } from "./knowledge-base";
import { fetchMemories, memoryCategoryLabel } from "./memory";
import { fetchWorkspaceTree } from "./workspace";

export type ContextMentionType = "workspace" | "kb" | "memory";

export type ContextMentionItem = {
  id: string;
  type: ContextMentionType;
  label: string;
  description: string;
  /** Token inserted into the message, e.g. @workspace:path/to/file */
  token: string;
};

const typeLabel: Record<ContextMentionType, string> = {
  workspace: "Workspace",
  kb: "Knowledge",
  memory: "Memory",
};

export function contextMentionTypeLabel(type: ContextMentionType): string {
  return typeLabel[type];
}

export async function fetchContextMentions(
  accessToken: string,
): Promise<ContextMentionItem[]> {
  const [workspaceResult, documents, memories] = await Promise.all([
    fetchWorkspaceTree(accessToken).catch(() => ({
      root: "",
      entries: [] as { path: string; name: string; type: string }[],
    })),
    fetchKnowledgeBaseDocuments(accessToken).catch(() => []),
    fetchMemories(accessToken).catch(() => []),
  ]);

  const items: ContextMentionItem[] = [];

  for (const entry of workspaceResult.entries) {
    if (entry.type !== "file") continue;
    items.push({
      id: `workspace:${entry.path}`,
      type: "workspace",
      label: entry.name,
      description: entry.path,
      token: `@workspace:${entry.path}`,
    });
  }

  for (const doc of documents) {
    if (doc.status !== "ingested") continue;
    const title = doc.meta.title?.trim() || doc.filename;
    items.push({
      id: `kb:${doc.id}`,
      type: "kb",
      label: title,
      description: doc.filename,
      token: `@kb:${doc.id}`,
    });
  }

  for (const memory of memories) {
    const preview =
      memory.content.length > 80
        ? `${memory.content.slice(0, 77)}…`
        : memory.content;
    items.push({
      id: `memory:${memory.id}`,
      type: "memory",
      label: memoryCategoryLabel[memory.category],
      description: preview,
      token: `@memory:${memory.id}`,
    });
  }

  items.sort((a, b) => {
    if (a.type !== b.type) return a.type.localeCompare(b.type);
    return a.label.localeCompare(b.label);
  });

  return items;
}

export function filterContextMentions(
  items: ContextMentionItem[],
  query: string,
): ContextMentionItem[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter(
    item =>
      item.label.toLowerCase().includes(q) ||
      item.description.toLowerCase().includes(q) ||
      item.token.toLowerCase().includes(q),
  );
}
