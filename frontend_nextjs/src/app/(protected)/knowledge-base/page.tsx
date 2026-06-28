"use client"

import {
  CheckCircle2Icon,
  DatabaseIcon,
  FileTextIcon,
  Loader2Icon,
  UploadCloudIcon,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { AppSidebar } from "@/components/app-sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { getToken } from "@/lib/auth"
import {
  fetchKnowledgeBaseDocument,
  fetchKnowledgeBaseDocumentFile,
  fetchKnowledgeBaseDocuments,
  fetchKnowledgeBaseOptions,
  fetchKnowledgeBaseStoredChunks,
  defaultDocumentAccess,
  defaultDocumentMetadata,
  ingestKnowledgeBaseDocument,
  previewKnowledgeBaseChunks,
  updateKnowledgeBaseDocumentSettings,
  uploadKnowledgeBaseDocument,
  visibilityLabel,
  type ChunkingStrategyId,
  type DocumentAccessControl,
  type DocumentMetadata,
  type DocumentSummary,
  type DocumentUploadResult,
  type EmbeddingModelId,
  type KnowledgeBaseOptions,
  type PreviewChunksResult,
  type Visibility,
} from "@/lib/knowledge-base"
import { cn } from "@/lib/utils"

function formatStrategy(id: string | null | undefined): string {
  if (!id) return "—"
  return id.replace(/_/g, " ")
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function statusBadge(status: DocumentSummary["status"]) {
  if (status === "ingested") {
    return (
      <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-700">
        Indexed
      </Badge>
    )
  }
  if (status === "failed") {
    return <Badge variant="destructive">Failed</Badge>
  }
  return <Badge variant="outline">Pending</Badge>
}

export default function KnowledgeBasePage() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [options, setOptions] = useState<KnowledgeBaseOptions | null>(null)
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [activeDoc, setActiveDoc] = useState<DocumentUploadResult | null>(null)
  const [activeSummary, setActiveSummary] = useState<DocumentSummary | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [chunkStrategy, setChunkStrategy] = useState<ChunkingStrategyId>("recursive")
  const [embeddingModel, setEmbeddingModel] =
    useState<EmbeddingModelId>("text-embedding-004")
  const [chunkSize, setChunkSize] = useState(1000)
  const [chunkOverlap, setChunkOverlap] = useState(200)
  const [chunkPreview, setChunkPreview] = useState<PreviewChunksResult | null>(null)
  const [storedChunks, setStoredChunks] = useState<PreviewChunksResult | null>(null)
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [loadingDocuments, setLoadingDocuments] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [libraryFilter, setLibraryFilter] = useState<"all" | "pending" | "indexed">("all")
  const [docMeta, setDocMeta] = useState<DocumentMetadata>(defaultDocumentMetadata())
  const [docAccess, setDocAccess] = useState<DocumentAccessControl>(defaultDocumentAccess())
  const [tagsInput, setTagsInput] = useState("")
  const [canManage, setCanManage] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)

  const indexedDocuments = useMemo(
    () => documents.filter(d => d.status === "ingested"),
    [documents],
  )

  const pendingDocuments = useMemo(
    () => documents.filter(d => d.status === "uploaded"),
    [documents],
  )

  const filteredLibrary = useMemo(() => {
    if (libraryFilter === "indexed") return indexedDocuments
    if (libraryFilter === "pending") return pendingDocuments
    return documents
  }, [documents, indexedDocuments, pendingDocuments, libraryFilter])

  const selectedStrategy = useMemo(
    () => options?.chunking_strategies.find(s => s.id === chunkStrategy),
    [options, chunkStrategy],
  )

  const showChunkControls =
    selectedStrategy?.supports_chunk_size !== false &&
    chunkStrategy !== "by_page"

  const refreshDocuments = useCallback(async () => {
    const token = getToken()
    if (!token) return []
    const docs = await fetchKnowledgeBaseDocuments(token)
    setDocuments(docs)
    return docs
  }, [])

  const loadInitial = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoadingOptions(true)
    setLoadingDocuments(true)
    setError(null)
    try {
      const [opts, docs] = await Promise.all([
        fetchKnowledgeBaseOptions(token),
        fetchKnowledgeBaseDocuments(token),
      ])
      setOptions(opts)
      setDocuments(docs)
      const defaultStrategy =
        opts.chunking_strategies.find(s => s.id === "recursive") ??
        opts.chunking_strategies[0]
      if (defaultStrategy) {
        setChunkSize(defaultStrategy.default_chunk_size)
        setChunkOverlap(defaultStrategy.default_chunk_overlap)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load knowledge base")
    } finally {
      setLoadingOptions(false)
      setLoadingDocuments(false)
    }
  }, [])

  useEffect(() => {
    void loadInitial()
  }, [loadInitial])

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    }
  }, [pdfUrl])

  useEffect(() => {
    if (!selectedStrategy) return
    if (!selectedStrategy.supports_chunk_size) return
    setChunkSize(selectedStrategy.default_chunk_size)
    setChunkOverlap(selectedStrategy.default_chunk_overlap)
  }, [selectedStrategy])

  const applyDocumentSettings = useCallback(
    (meta: DocumentMetadata, access: DocumentAccessControl, manage: boolean) => {
      setDocMeta(meta)
      setDocAccess(access)
      setTagsInput(meta.tags.join(", "))
      setCanManage(manage)
    },
    [],
  )

  const buildSettingsPayload = useCallback((): {
    meta: DocumentMetadata
    access: DocumentAccessControl
  } => {
    const tags = tagsInput
      .split(",")
      .map(t => t.trim())
      .filter(Boolean)
    return {
      meta: { ...docMeta, tags },
      access: docAccess,
    }
  }, [docMeta, docAccess, tagsInput])

  const loadPdfPreview = useCallback(async (documentId: string) => {
    const token = getToken()
    if (!token) return
    const blob = await fetchKnowledgeBaseDocumentFile(token, documentId)
    const url = URL.createObjectURL(blob)
    setPdfUrl(prev => {
      if (prev) URL.revokeObjectURL(prev)
      return url
    })
  }, [])

  const openDocument = async (doc: DocumentSummary) => {
    const token = getToken()
    if (!token) return
    setError(null)
    setSuccess(null)
    setChunkPreview(null)
    setStoredChunks(null)
    setActiveSummary(doc)
    try {
      const detail = await fetchKnowledgeBaseDocument(token, doc.id)
      setActiveDoc({
        id: detail.id,
        filename: detail.filename,
        content_type: detail.content_type,
        page_count: detail.page_count,
        char_count: detail.pages.reduce((n, p) => n + p.text.length, 0),
        pages: detail.pages,
        status: detail.status,
        created_at: detail.created_at,
      })
      setActiveSummary({
        id: detail.id,
        filename: detail.filename,
        content_type: detail.content_type,
        page_count: detail.page_count,
        status: detail.status,
        chunk_count: detail.chunk_count,
        chunking_strategy: detail.chunking_strategy,
        embedding_model: detail.embedding_model,
        created_at: detail.created_at,
        ingested_at: detail.ingested_at,
        meta: detail.meta,
        access: detail.access,
        is_owner: detail.is_owner,
      })
      applyDocumentSettings(detail.meta, detail.access, detail.can_manage)
      await loadPdfPreview(doc.id)
      if (detail.chunking_strategy) setChunkStrategy(detail.chunking_strategy)
      if (detail.embedding_model) setEmbeddingModel(detail.embedding_model)
      if (detail.status === "ingested") {
        const stored = await fetchKnowledgeBaseStoredChunks(token, doc.id)
        setStoredChunks(stored)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open document")
    }
  }

  const handleUpload = async (file: File) => {
    const token = getToken()
    if (!token) return
    if (file.type !== "application/pdf") {
      setError("Only PDF files are supported.")
      return
    }
    setUploading(true)
    setError(null)
    setSuccess(null)
    setChunkPreview(null)
    setStoredChunks(null)
    setActiveSummary(null)
    try {
      const settings = buildSettingsPayload()
      const result = await uploadKnowledgeBaseDocument(token, file, settings)
      setActiveDoc(result)
      setActiveSummary({
        id: result.id,
        filename: result.filename,
        content_type: result.content_type,
        page_count: result.page_count,
        status: result.status,
        chunk_count: null,
        chunking_strategy: null,
        embedding_model: null,
        created_at: result.created_at,
        ingested_at: null,
        meta: result.meta,
        access: result.access,
        is_owner: true,
      })
      applyDocumentSettings(result.meta, result.access, true)
      await loadPdfPreview(result.id)
      await refreshDocuments()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  const handlePreviewChunks = async () => {
    if (!activeDoc) return
    const token = getToken()
    if (!token) return
    setPreviewing(true)
    setError(null)
    try {
      const preview = await previewKnowledgeBaseChunks(token, activeDoc.id, {
        chunking_strategy: chunkStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
      })
      setChunkPreview(preview)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chunk preview failed")
    } finally {
      setPreviewing(false)
    }
  }

  const handleSaveSettings = async () => {
    if (!activeDoc || !canManage || isIndexed) return
    const token = getToken()
    if (!token) return
    setSavingSettings(true)
    setError(null)
    setSuccess(null)
    try {
      const payload = buildSettingsPayload()
      const detail = await updateKnowledgeBaseDocumentSettings(
        token,
        activeDoc.id,
        payload,
      )
      applyDocumentSettings(detail.meta, detail.access, detail.can_manage)
      setActiveSummary(prev =>
        prev
          ? {
              ...prev,
              meta: detail.meta,
              access: detail.access,
            }
          : prev,
      )
      await refreshDocuments()
      setSuccess("Document metadata and access settings saved.")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save settings")
    } finally {
      setSavingSettings(false)
    }
  }

  const handleIngest = async () => {
    if (!activeDoc) return
    const token = getToken()
    if (!token) return
    setIngesting(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await ingestKnowledgeBaseDocument(token, activeDoc.id, {
        chunking_strategy: chunkStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        embedding_model: embeddingModel,
      })
      setSuccess(
        `Indexed ${result.chunk_count} chunks with ${result.embedding_model}.`,
      )
      const docs = await refreshDocuments()
      const updated = docs.find(d => d.id === activeDoc.id)
      if (updated) {
        setActiveSummary(updated)
        setActiveDoc(prev =>
          prev ? { ...prev, status: "ingested" } : prev,
        )
        const stored = await fetchKnowledgeBaseStoredChunks(token, activeDoc.id)
        setStoredChunks(stored)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingest failed")
    } finally {
      setIngesting(false)
    }
  }

  const chunksToShow = storedChunks ?? chunkPreview
  const isIndexed = activeSummary?.status === "ingested"

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <h1 className="text-lg font-semibold">Knowledge Base</h1>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 lg:p-6">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}
          {success ? (
            <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-800 dark:text-emerald-300">
              <CheckCircle2Icon className="size-4 shrink-0" />
              {success}
            </div>
          ) : null}

          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <DatabaseIcon className="size-4 text-muted-foreground" />
                    Indexed documents
                  </CardTitle>
                  <CardDescription>
                    PDFs that have been chunked and embedded into the knowledge base
                  </CardDescription>
                </div>
                <Badge variant="secondary">{indexedDocuments.length} indexed</Badge>
              </div>
            </CardHeader>
            <CardContent>
              {loadingDocuments ? (
                <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                  <Loader2Icon className="size-4 animate-spin" />
                  Loading documents…
                </div>
              ) : indexedDocuments.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">
                  No indexed documents yet. Upload a PDF, configure chunking, then click
                  &quot;Ingest document&quot;.
                </p>
              ) : (
                <ScrollArea className="max-h-[280px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Document</TableHead>
                        <TableHead className="hidden sm:table-cell">Pages</TableHead>
                        <TableHead>Chunks</TableHead>
                        <TableHead className="hidden sm:table-cell">Access</TableHead>
                        <TableHead className="hidden md:table-cell">Strategy</TableHead>
                        <TableHead className="hidden lg:table-cell">Model</TableHead>
                        <TableHead className="hidden md:table-cell">Indexed</TableHead>
                        <TableHead className="w-[80px]" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {indexedDocuments.map(doc => (
                        <TableRow
                          key={doc.id}
                          className={cn(
                            activeDoc?.id === doc.id && "bg-muted/40",
                          )}
                        >
                          <TableCell className="max-w-[200px] truncate font-medium">
                            {doc.meta.title || doc.filename}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {doc.page_count}
                          </TableCell>
                          <TableCell>{doc.chunk_count ?? "—"}</TableCell>
                          <TableCell className="hidden sm:table-cell">
                            <Badge variant="outline" className="font-normal">
                              {visibilityLabel(
                                doc.access.visibility,
                                options?.access_visibility_options,
                              )}
                            </Badge>
                          </TableCell>
                          <TableCell className="hidden capitalize md:table-cell">
                            {formatStrategy(doc.chunking_strategy)}
                          </TableCell>
                          <TableCell className="hidden max-w-[140px] truncate lg:table-cell text-xs text-muted-foreground">
                            {doc.embedding_model ?? "—"}
                          </TableCell>
                          <TableCell className="hidden whitespace-nowrap text-xs text-muted-foreground md:table-cell">
                            {formatDate(doc.ingested_at)}
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => void openDocument(doc)}
                            >
                              Open
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              )}
            </CardContent>
          </Card>

          <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Upload</CardTitle>
                  <CardDescription>PDF documents only (max 25 MB)</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf"
                    className="hidden"
                    onChange={e => {
                      const file = e.target.files?.[0]
                      if (file) void handleUpload(file)
                      e.target.value = ""
                    }}
                  />
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={e => e.preventDefault()}
                    onDrop={e => {
                      e.preventDefault()
                      const file = e.dataTransfer.files?.[0]
                      if (file) void handleUpload(file)
                    }}
                    className={cn(
                      "flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors",
                      "hover:border-primary/50 hover:bg-muted/40",
                      uploading && "pointer-events-none opacity-60",
                    )}
                  >
                    {uploading ? (
                      <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    ) : (
                      <UploadCloudIcon className="size-8 text-muted-foreground" />
                    )}
                    <span className="text-sm font-medium">
                      {uploading ? "Uploading…" : "Drop PDF or click to browse"}
                    </span>
                  </button>
                  {activeDoc ? (
                    <div className="rounded-md bg-muted/40 px-3 py-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium truncate">
                          {activeSummary?.meta.title || activeDoc.filename}
                        </p>
                        {activeSummary ? statusBadge(activeSummary.status) : null}
                      </div>
                      <p className="text-muted-foreground">
                        {activeDoc.page_count} pages · {activeDoc.char_count.toLocaleString()} chars
                      </p>
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Metadata & access</CardTitle>
                  <CardDescription>
                    Title, tags, and who can read this document after indexing
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="doc-title">Title</Label>
                    <Input
                      id="doc-title"
                      value={docMeta.title}
                      disabled={!activeDoc || isIndexed || !canManage}
                      onChange={e =>
                        setDocMeta(prev => ({ ...prev, title: e.target.value }))
                      }
                      placeholder="Display name for this document"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="doc-description">Description</Label>
                    <Textarea
                      id="doc-description"
                      value={docMeta.description}
                      disabled={!activeDoc || isIndexed || !canManage}
                      onChange={e =>
                        setDocMeta(prev => ({
                          ...prev,
                          description: e.target.value,
                        }))
                      }
                      rows={3}
                      placeholder="Optional summary or notes"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="doc-tags">Tags</Label>
                    <Input
                      id="doc-tags"
                      value={tagsInput}
                      disabled={!activeDoc || isIndexed || !canManage}
                      onChange={e => setTagsInput(e.target.value)}
                      placeholder="finance, policy, onboarding"
                    />
                    <p className="text-xs text-muted-foreground">
                      Comma-separated. Stored on the document and copied to chunks at ingest.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Visibility</Label>
                    <Select
                      value={docAccess.visibility}
                      disabled={!activeDoc || isIndexed || !canManage}
                      onValueChange={v =>
                        setDocAccess(prev => ({
                          ...prev,
                          visibility: v as Visibility,
                          allowed_group_ids:
                            v === "group" ? prev.allowed_group_ids : [],
                          allowed_roles: v === "role" ? prev.allowed_roles : [],
                        }))
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {options?.access_visibility_options.map(o => (
                          <SelectItem key={o.id} value={o.id}>
                            {o.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {options?.access_visibility_options.find(
                      o => o.id === docAccess.visibility,
                    ) ? (
                      <p className="text-xs text-muted-foreground">
                        {
                          options.access_visibility_options.find(
                            o => o.id === docAccess.visibility,
                          )?.description
                        }
                      </p>
                    ) : null}
                  </div>
                  {docAccess.visibility === "group" ? (
                    <div className="space-y-2">
                      <Label>Allowed groups</Label>
                      {(options?.groups.length ?? 0) === 0 ? (
                        <p className="text-xs text-muted-foreground">
                          You are not a member of any groups yet.
                        </p>
                      ) : (
                        <div className="space-y-2 rounded-md border p-3">
                          {options?.groups.map(group => {
                            const checked = docAccess.allowed_group_ids.includes(
                              group.id,
                            )
                            return (
                              <label
                                key={group.id}
                                className="flex cursor-pointer items-center gap-2 text-sm"
                              >
                                <Checkbox
                                  checked={checked}
                                  disabled={!activeDoc || isIndexed || !canManage}
                                  onCheckedChange={value => {
                                    setDocAccess(prev => ({
                                      ...prev,
                                      allowed_group_ids: value
                                        ? [...prev.allowed_group_ids, group.id]
                                        : prev.allowed_group_ids.filter(
                                            id => id !== group.id,
                                          ),
                                    }))
                                  }}
                                />
                                {group.name}
                              </label>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  ) : null}
                  {docAccess.visibility === "role" ? (
                    <div className="space-y-2">
                      <Label>Allowed roles</Label>
                      <div className="space-y-2 rounded-md border p-3">
                        {options?.role_options.map(role => {
                          const checked = docAccess.allowed_roles.includes(role.id)
                          return (
                            <label
                              key={role.id}
                              className="flex cursor-pointer items-center gap-2 text-sm"
                            >
                              <Checkbox
                                checked={checked}
                                disabled={!activeDoc || isIndexed || !canManage}
                                onCheckedChange={value => {
                                  setDocAccess(prev => ({
                                    ...prev,
                                    allowed_roles: value
                                      ? [...prev.allowed_roles, role.id]
                                      : prev.allowed_roles.filter(
                                          id => id !== role.id,
                                        ),
                                  }))
                                }}
                              />
                              {role.label}
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  ) : null}
                  {!canManage && activeDoc && !isIndexed ? (
                    <p className="text-xs text-muted-foreground">
                      Only the document owner can edit metadata and access.
                    </p>
                  ) : null}
                  {isIndexed && activeDoc ? (
                    <p className="text-xs text-muted-foreground">
                      Metadata and access are locked after indexing.
                    </p>
                  ) : (
                    <Button
                      variant="outline"
                      className="w-full"
                      disabled={!activeDoc || !canManage || savingSettings}
                      onClick={() => void handleSaveSettings()}
                    >
                      {savingSettings ? (
                        <>
                          <Loader2Icon className="size-4 animate-spin" />
                          Saving…
                        </>
                      ) : (
                        "Save metadata & access"
                      )}
                    </Button>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Ingest settings</CardTitle>
                  <CardDescription>Choose how to split and embed</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {loadingOptions ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2Icon className="size-4 animate-spin" />
                      Loading options…
                    </div>
                  ) : (
                    <>
                      <div className="space-y-2">
                        <Label>Chunking strategy</Label>
                        <Select
                          value={chunkStrategy}
                          onValueChange={v => setChunkStrategy(v as ChunkingStrategyId)}
                          disabled={isIndexed}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {options?.chunking_strategies.map(s => (
                              <SelectItem key={s.id} value={s.id}>
                                {s.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {selectedStrategy ? (
                          <p className="text-xs text-muted-foreground">
                            {selectedStrategy.description}
                          </p>
                        ) : null}
                      </div>

                      {showChunkControls ? (
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-2">
                            <Label htmlFor="chunk-size">Chunk size</Label>
                            <Input
                              id="chunk-size"
                              type="number"
                              min={200}
                              max={8000}
                              value={chunkSize}
                              disabled={isIndexed}
                              onChange={e => setChunkSize(Number(e.target.value))}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="chunk-overlap">Overlap</Label>
                            <Input
                              id="chunk-overlap"
                              type="number"
                              min={0}
                              max={2000}
                              value={chunkOverlap}
                              disabled={isIndexed}
                              onChange={e => setChunkOverlap(Number(e.target.value))}
                            />
                          </div>
                        </div>
                      ) : null}

                      <div className="space-y-2">
                        <Label>Embedding model</Label>
                        <Select
                          value={embeddingModel}
                          onValueChange={v => setEmbeddingModel(v as EmbeddingModelId)}
                          disabled={isIndexed}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {options?.embedding_models.map(m => (
                              <SelectItem key={m.id} value={m.id}>
                                {m.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="flex flex-col gap-2 pt-1">
                        <Button
                          variant="outline"
                          disabled={!activeDoc || previewing || isIndexed}
                          onClick={() => void handlePreviewChunks()}
                        >
                          {previewing ? (
                            <>
                              <Loader2Icon className="size-4 animate-spin" />
                              Previewing…
                            </>
                          ) : (
                            "Preview chunks"
                          )}
                        </Button>
                        <Button
                          disabled={!activeDoc || ingesting || isIndexed}
                          onClick={() => void handleIngest()}
                        >
                          {ingesting ? (
                            <>
                              <Loader2Icon className="size-4 animate-spin" />
                              Ingesting…
                            </>
                          ) : isIndexed ? (
                            "Already indexed"
                          ) : (
                            "Ingest document"
                          )}
                        </Button>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              <Card className="min-h-0 flex-1">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">All documents</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 p-0 px-4 pb-4">
                  <Tabs
                    value={libraryFilter}
                    onValueChange={v => setLibraryFilter(v as typeof libraryFilter)}
                  >
                    <TabsList className="grid w-full grid-cols-3">
                      <TabsTrigger value="all">All ({documents.length})</TabsTrigger>
                      <TabsTrigger value="pending">
                        Pending ({pendingDocuments.length})
                      </TabsTrigger>
                      <TabsTrigger value="indexed">
                        Indexed ({indexedDocuments.length})
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                  <ScrollArea className="h-[180px]">
                    {filteredLibrary.length === 0 ? (
                      <p className="py-4 text-sm text-muted-foreground">
                        No documents in this view.
                      </p>
                    ) : (
                      <ul className="space-y-2 pr-3">
                        {filteredLibrary.map(doc => (
                          <li key={doc.id}>
                            <button
                              type="button"
                              onClick={() => void openDocument(doc)}
                              className={cn(
                                "flex w-full items-start justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50",
                                activeDoc?.id === doc.id && "border-primary/40 bg-muted/40",
                              )}
                            >
                              <span className="min-w-0">
                                <span className="block truncate font-medium">
                                  {doc.meta.title || doc.filename}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {doc.page_count} pages
                                  {doc.chunk_count != null
                                    ? ` · ${doc.chunk_count} chunks`
                                    : ""}
                                  {doc.ingested_at
                                    ? ` · ${formatDate(doc.ingested_at)}`
                                    : ""}
                                </span>
                              </span>
                              {statusBadge(doc.status)}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>

            <Card className="flex min-h-[520px] min-w-0 flex-col">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Preview</CardTitle>
                <CardDescription>
                  Review the PDF, extracted text, and chunks
                </CardDescription>
                {isIndexed && activeSummary ? (
                  <div className="mt-2 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">Indexed · </span>
                    {activeSummary.chunk_count} chunks ·{" "}
                    {formatStrategy(activeSummary.chunking_strategy)} ·{" "}
                    {activeSummary.embedding_model} · {formatDate(activeSummary.ingested_at)}
                  </div>
                ) : null}
              </CardHeader>
              <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
                {!activeDoc ? (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
                    <FileTextIcon className="size-10 opacity-40" />
                    <p className="text-sm">Upload a PDF or open an indexed document</p>
                  </div>
                ) : (
                  <Tabs defaultValue="pdf" className="flex min-h-0 flex-1 flex-col">
                    <TabsList>
                      <TabsTrigger value="pdf">PDF</TabsTrigger>
                      <TabsTrigger value="text">Extracted text</TabsTrigger>
                      <TabsTrigger value="chunks">
                        {isIndexed ? "Stored chunks" : "Chunks"}
                      </TabsTrigger>
                    </TabsList>
                    <TabsContent value="pdf" className="min-h-0 flex-1">
                      {pdfUrl ? (
                        <iframe
                          title="PDF preview"
                          src={pdfUrl}
                          className="h-[min(60vh,640px)] w-full rounded-md border bg-muted/20"
                        />
                      ) : (
                        <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
                          <Loader2Icon className="mr-2 size-4 animate-spin" />
                          Loading preview…
                        </div>
                      )}
                    </TabsContent>
                    <TabsContent value="text" className="min-h-0 flex-1">
                      <ScrollArea className="h-[min(60vh,640px)] rounded-md border p-4">
                        {activeDoc.pages.length > 0 ? (
                          <div className="space-y-4 text-sm">
                            {activeDoc.pages.map(p => (
                              <div key={p.page}>
                                <p className="mb-1 text-xs font-medium text-muted-foreground">
                                  Page {p.page}
                                </p>
                                <p className="whitespace-pre-wrap">{p.text || "—"}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            Open a document from the library to view extracted text.
                          </p>
                        )}
                      </ScrollArea>
                    </TabsContent>
                    <TabsContent value="chunks" className="min-h-0 flex-1">
                      <ScrollArea className="h-[min(60vh,640px)] rounded-md border p-4">
                        {!chunksToShow ? (
                          <p className="text-sm text-muted-foreground">
                            {isIndexed
                              ? "No stored chunks found."
                              : 'Click "Preview chunks" to see how the document will be split.'}
                          </p>
                        ) : (
                          <div className="space-y-3">
                            <p className="text-xs text-muted-foreground">
                              {storedChunks ? "Stored in knowledge base · " : ""}
                              Showing {chunksToShow.preview.length} of{" "}
                              {chunksToShow.total_chunks} chunks
                            </p>
                            {chunksToShow.preview.map(c => (
                              <div
                                key={c.index}
                                className="rounded-md border bg-muted/20 px-3 py-2 text-sm"
                              >
                                <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                                  <span>#{c.index + 1}</span>
                                  {c.page != null ? <span>page {c.page}</span> : null}
                                  <span>{c.char_count} chars</span>
                                </div>
                                <p className="whitespace-pre-wrap">{c.text}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </ScrollArea>
                    </TabsContent>
                  </Tabs>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
