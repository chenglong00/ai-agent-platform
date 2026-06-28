"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Loader2Icon, RefreshCwIcon } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { WorkspaceChangedFilesSummary } from "@/components/workspace/changed-files-summary"
import { WorkspaceChatPanel } from "@/components/workspace/chat-panel"
import { WorkspaceCodePanel } from "@/components/workspace/code-panel"
import { WorkspaceFileTree } from "@/components/workspace/file-tree"
import { Button } from "@/components/ui/button"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { getToken } from "@/lib/auth"
import {
  buildWorkspaceTree,
  fetchWorkspaceFile,
  fetchWorkspaceRoot,
  fetchWorkspaceTree,
  type WorkspaceEntry,
  type WorkspaceTreeNode,
} from "@/lib/workspace"

export default function WorkspacePage() {
  const [entries, setEntries] = useState<WorkspaceEntry[]>([])
  const [files, setFiles] = useState<Map<string, string>>(new Map())
  const [originals, setOriginals] = useState<Map<string, string>>(new Map())
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [selectedLoading, setSelectedLoading] = useState(false)
  const [treeLoading, setTreeLoading] = useState(true)
  const [workspaceRoot, setWorkspaceRoot] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const initialSnapshotTaken = useRef(false)
  const refreshInFlight = useRef<Promise<void> | null>(null)

  const tree: WorkspaceTreeNode[] = useMemo(
    () => buildWorkspaceTree(entries),
    [entries],
  )

  const changedPaths = useMemo(() => {
    const set = new Set<string>()
    for (const [path, content] of files.entries()) {
      const original = originals.get(path)
      if (original === undefined || original !== content) {
        // Only flag as "changed" if we actually had an original snapshot.
        if (original !== undefined && original !== content) set.add(path)
      }
    }
    for (const path of originals.keys()) {
      if (!files.has(path)) set.add(path)
    }
    return set
  }, [files, originals])

  const refreshTree = useCallback(
    async (
      opts: { selectFirstFile?: boolean; resetSnapshot?: boolean } = {},
    ) => {
      if (refreshInFlight.current) {
        return refreshInFlight.current
      }
      const run = (async () => {
      const token = getToken()
      if (!token) return
      setTreeLoading(true)
      setError(null)
      try {
        const rootInfo = await fetchWorkspaceRoot(token)
        setWorkspaceRoot(rootInfo.root)
        const result = await fetchWorkspaceTree(token)
        setEntries(result.entries)

        if (opts.resetSnapshot || !initialSnapshotTaken.current) {
          setOriginals(new Map())
          setFiles(new Map())
          initialSnapshotTaken.current = true
        }

        if (opts.selectFirstFile && !selectedPath) {
          const first = result.entries.find(e => e.type === "file")
          if (first) setSelectedPath(first.path)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load workspace")
      } finally {
        setTreeLoading(false)
      }
      })()
      refreshInFlight.current = run
      try {
        await run
      } finally {
        if (refreshInFlight.current === run) {
          refreshInFlight.current = null
        }
      }
    },
    [selectedPath],
  )

  useEffect(() => {
    void refreshTree({ selectFirstFile: true, resetSnapshot: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!selectedPath) return
    const token = getToken()
    if (!token) return
    let cancelled = false
    setSelectedLoading(true)
    void fetchWorkspaceFile(token, selectedPath)
      .then(file => {
        if (cancelled || file.binary) return
        setFiles(prev => {
          const next = new Map(prev)
          next.set(file.path, file.content)
          return next
        })
        setOriginals(prev => {
          if (prev.has(file.path)) return prev
          const next = new Map(prev)
          next.set(file.path, file.content)
          return next
        })
      })
      .catch(() => {
        /* ignore — error banner handled on tree refresh */
      })
      .finally(() => {
        if (!cancelled) setSelectedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedPath])

  const reloadSelectedFile = useCallback(async () => {
    const token = getToken()
    if (!token || !selectedPath) return
    setSelectedLoading(true)
    try {
      const file = await fetchWorkspaceFile(token, selectedPath)
      if (file.binary) return
      setFiles(prev => {
        const next = new Map(prev)
        next.set(file.path, file.content)
        return next
      })
    } catch {
      /* ignore */
    } finally {
      setSelectedLoading(false)
    }
  }, [selectedPath])

  const onTurnComplete = useCallback(() => {
    // Refresh tree + all file contents, but DON'T overwrite the original
    // snapshot — that's how we keep diff markers across the chat session.
    void refreshTree()
    void reloadSelectedFile()
  }, [refreshTree, reloadSelectedFile])

  const handleResetBaseline = () => {
    setOriginals(new Map(files))
  }

  const currentContent = selectedPath ? files.get(selectedPath) ?? null : null
  const originalContent = selectedPath ? originals.get(selectedPath) ?? null : null
  const isChanged = selectedPath ? changedPaths.has(selectedPath) : false

  return (
    <SidebarProvider
      className="h-svh min-h-0 overflow-hidden"
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset className="min-h-0 overflow-hidden">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="shrink-0 md:hidden" />
          <h1 className="text-base font-medium">Workspace</h1>
          <span className="ml-2 truncate text-xs text-muted-foreground">
            {workspaceRoot ?? "Loading workspace root…"}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={handleResetBaseline}
              disabled={files.size === 0}
              title="Treat current contents as the new baseline (clears diff markers)"
            >
              Reset baseline
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void refreshTree()}
              disabled={treeLoading}
            >
              {treeLoading ? (
                <Loader2Icon className="mr-1.5 size-3.5 animate-spin" />
              ) : (
                <RefreshCwIcon className="mr-1.5 size-3.5" />
              )}
              Refresh
            </Button>
          </div>
        </header>

        {error ? (
          <div
            className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive"
            role="alert"
          >
            {error}
          </div>
        ) : null}

        <ResizablePanelGroup
          direction="horizontal"
          autoSaveId="workspace-layout"
          className="min-h-0 flex-1 overflow-hidden"
        >
          <ResizablePanel
            defaultSize={20}
            minSize={12}
            maxSize={40}
            className="flex min-h-0 flex-col"
          >
            <div className="min-h-0 flex-1">
              <WorkspaceFileTree
                nodes={tree}
                selectedPath={selectedPath}
                changedPaths={changedPaths}
                onSelect={setSelectedPath}
                isLoading={treeLoading && entries.length === 0}
              />
            </div>
            <WorkspaceChangedFilesSummary
              changedPaths={Array.from(changedPaths)}
              current={files}
              original={originals}
              onSelect={setSelectedPath}
            />
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel
            defaultSize={55}
            minSize={25}
            className="flex min-h-0 flex-col"
          >
            <WorkspaceCodePanel
              selectedPath={selectedPath}
              currentContent={currentContent}
              originalContent={originalContent}
              isChanged={isChanged}
              isLoading={selectedLoading}
              isWaiting={treeLoading && !selectedPath}
            />
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel
            defaultSize={25}
            minSize={18}
            maxSize={50}
            className="flex min-h-0 flex-col"
          >
            <WorkspaceChatPanel
              onTurnComplete={onTurnComplete}
              workspaceRoot={workspaceRoot}
              selectedPath={selectedPath}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </SidebarInset>
    </SidebarProvider>
  )
}
