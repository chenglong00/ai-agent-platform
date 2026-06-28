import { apiBaseUrl, parseApiErrorMessage } from "./api";

const kbBase = `${apiBaseUrl}/api/v1/knowledge-base`;

export type ChunkingStrategyId = "fixed_size" | "recursive" | "by_page";
export type ParsingStrategyId = "pypdf" | "gemini";
export type EmbeddingModelId =
  | "text-embedding-004"
  | "text-embedding-005"
  | "textembedding-gecko@003";
export type DocumentStatus = "uploaded" | "ingested" | "failed";
export type Visibility = "private" | "organization" | "group" | "role";

export type ParsingStrategyOption = {
  id: ParsingStrategyId;
  label: string;
  description: string;
};

export type ChunkingStrategyOption = {
  id: ChunkingStrategyId;
  label: string;
  description: string;
  supports_chunk_size: boolean;
  supports_chunk_overlap: boolean;
  default_chunk_size: number;
  default_chunk_overlap: number;
};

export type EmbeddingModelOption = {
  id: EmbeddingModelId;
  label: string;
  description: string;
  dimensions: number;
};

export type AccessVisibilityOption = {
  id: Visibility;
  label: string;
  description: string;
};

export type GroupOption = {
  id: string;
  name: string;
};

export type RoleOption = {
  id: string;
  label: string;
};

export type DocumentMetadata = {
  title: string;
  description: string;
  tags: string[];
  custom: Record<string, string>;
};

export type DocumentAccessControl = {
  visibility: Visibility;
  allowed_group_ids: string[];
  allowed_roles: string[];
};

export type DocumentSettingsRequest = {
  meta?: DocumentMetadata;
  access?: DocumentAccessControl;
};

export type KnowledgeBaseOptions = {
  parsing_strategies: ParsingStrategyOption[];
  chunking_strategies: ChunkingStrategyOption[];
  embedding_models: EmbeddingModelOption[];
  access_visibility_options: AccessVisibilityOption[];
  role_options: RoleOption[];
  groups: GroupOption[];
};

export type PagePreview = {
  page: number;
  text: string;
};

export type DocumentUploadResult = {
  id: string;
  filename: string;
  content_type: string;
  page_count: number;
  char_count: number;
  pages: PagePreview[];
  status: DocumentStatus;
  parsing_strategy: ParsingStrategyId;
  created_at: string;
  meta: DocumentMetadata;
  access: DocumentAccessControl;
};

export type DocumentSummary = {
  id: string;
  filename: string;
  content_type: string;
  page_count: number;
  status: DocumentStatus;
  parsing_strategy: ParsingStrategyId | null;
  chunk_count: number | null;
  chunking_strategy: ChunkingStrategyId | null;
  embedding_model: EmbeddingModelId | null;
  created_at: string;
  ingested_at: string | null;
  meta: DocumentMetadata;
  access: DocumentAccessControl;
  is_owner: boolean;
};

export type ChunkPreview = {
  index: number;
  page: number | null;
  char_count: number;
  text: string;
};

export type PreviewChunksResult = {
  strategy: ChunkingStrategyId;
  chunk_size: number | null;
  chunk_overlap: number | null;
  total_chunks: number;
  preview: ChunkPreview[];
};

export type IngestResult = {
  id: string;
  status: DocumentStatus;
  chunk_count: number;
  chunking_strategy: ChunkingStrategyId;
  embedding_model: EmbeddingModelId;
  ingested_at: string;
};

export type DeleteDocumentResult = {
  id: string;
  deleted: boolean;
};

function authHeaders(accessToken: string, json = true): HeadersInit {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken.trim()}`,
  };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

export async function fetchKnowledgeBaseOptions(
  accessToken: string,
): Promise<KnowledgeBaseOptions> {
  const res = await fetch(`${kbBase}/options`, {
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<KnowledgeBaseOptions>;
}

export type DocumentDetail = DocumentSummary & {
  pages: PagePreview[];
  error_message: string | null;
  ingest_config: Record<string, unknown>;
  can_manage: boolean;
};

export async function fetchKnowledgeBaseDocument(
  accessToken: string,
  documentId: string,
): Promise<DocumentDetail> {
  const res = await fetch(
    `${kbBase}/documents/${encodeURIComponent(documentId)}`,
    {
      headers: authHeaders(accessToken, false),
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<DocumentDetail>;
}

export async function fetchKnowledgeBaseDocuments(
  accessToken: string,
): Promise<DocumentSummary[]> {
  const res = await fetch(`${kbBase}/documents`, {
    headers: authHeaders(accessToken, false),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<DocumentSummary[]>;
}

export async function uploadKnowledgeBaseDocument(
  accessToken: string,
  file: File,
  settings?: DocumentSettingsRequest,
  parsingStrategy: ParsingStrategyId = "pypdf",
): Promise<DocumentUploadResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("parsing_strategy", parsingStrategy);
  if (settings) {
    form.append("settings", JSON.stringify(settings));
  }
  const res = await fetch(`${kbBase}/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken.trim()}` },
    body: form,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<DocumentUploadResult>;
}

export async function updateKnowledgeBaseDocumentSettings(
  accessToken: string,
  documentId: string,
  body: DocumentSettingsRequest,
): Promise<DocumentDetail> {
  const res = await fetch(
    `${kbBase}/documents/${encodeURIComponent(documentId)}`,
    {
      method: "PATCH",
      headers: authHeaders(accessToken),
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<DocumentDetail>;
}

export async function fetchKnowledgeBaseDocumentFile(
  accessToken: string,
  documentId: string,
): Promise<Blob> {
  const res = await fetch(
    `${kbBase}/documents/${encodeURIComponent(documentId)}/file`,
    {
      headers: { Authorization: `Bearer ${accessToken.trim()}` },
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.blob();
}

export async function previewKnowledgeBaseChunks(
  accessToken: string,
  documentId: string,
  body: {
    chunking_strategy: ChunkingStrategyId;
    chunk_size: number;
    chunk_overlap: number;
  },
): Promise<PreviewChunksResult> {
  const res = await fetch(
    `${kbBase}/documents/${encodeURIComponent(documentId)}/preview-chunks`,
    {
      method: "POST",
      headers: authHeaders(accessToken),
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<PreviewChunksResult>;
}

export async function fetchKnowledgeBaseStoredChunks(
  accessToken: string,
  documentId: string,
  limit = 12,
): Promise<PreviewChunksResult> {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(
    `${kbBase}/documents/${encodeURIComponent(documentId)}/chunks?${params}`,
    {
      headers: authHeaders(accessToken, false),
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<PreviewChunksResult>;
}

export async function ingestKnowledgeBaseDocument(
  accessToken: string,
  documentId: string,
  body: {
    chunking_strategy: ChunkingStrategyId;
    chunk_size: number;
    chunk_overlap: number;
    embedding_model: EmbeddingModelId;
  },
): Promise<IngestResult> {
  const res = await fetch(
    `${kbBase}/documents/${encodeURIComponent(documentId)}/ingest`,
    {
      method: "POST",
      headers: authHeaders(accessToken),
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<IngestResult>;
}

export async function deleteKnowledgeBaseDocument(
  accessToken: string,
  documentId: string,
): Promise<DeleteDocumentResult> {
  const res = await fetch(
    `${kbBase}/documents/${encodeURIComponent(documentId)}`,
    {
      method: "DELETE",
      headers: authHeaders(accessToken, false),
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(await parseApiErrorMessage(res));
  return res.json() as Promise<DeleteDocumentResult>;
}

export function visibilityLabel(
  visibility: Visibility,
  options?: AccessVisibilityOption[],
): string {
  return options?.find(o => o.id === visibility)?.label ?? visibility;
}

export const defaultDocumentMetadata = (filename = ""): DocumentMetadata => ({
  title: filename,
  description: "",
  tags: [],
  custom: {},
});

export const defaultDocumentAccess = (): DocumentAccessControl => ({
  visibility: "private",
  allowed_group_ids: [],
  allowed_roles: [],
});
