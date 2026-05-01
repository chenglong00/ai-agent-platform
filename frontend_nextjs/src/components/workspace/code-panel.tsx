"use client"

import { useEffect, useMemo, useState } from "react"
import { CodeIcon, EyeIcon, Loader2Icon } from "lucide-react"

import { MessageResponse } from "@/components/ai/message"
import { cn } from "@/lib/utils"

import { WorkspaceFileIcon } from "./file-icon"

type CodePanelProps = {
  selectedPath: string | null
  currentContent: string | null
  originalContent: string | null
  isChanged: boolean
  isLoading?: boolean
  /** Shown when nothing is selected and we're still bootstrapping. */
  isWaiting?: boolean
}

type Mode = "preview" | "code" | "diff"
type PreviewKind = "html" | "markdown" | null

/** Decide whether a file has a richer "Preview" view in addition to source. */
function getPreviewKind(name: string): PreviewKind {
  const ext = name.includes(".") ? name.split(".").pop()!.toLowerCase() : ""
  if (ext === "html" || ext === "htm") return "html"
  if (ext === "md" || ext === "markdown" || ext === "mdx") return "markdown"
  return null
}

export function WorkspaceCodePanel({
  selectedPath,
  currentContent,
  originalContent,
  isChanged,
  isLoading,
  isWaiting,
}: CodePanelProps) {
  const name = selectedPath ? (selectedPath.split("/").pop() ?? selectedPath) : ""
  const previewKind = selectedPath ? getPreviewKind(name) : null
  const [mode, setMode] = useState<Mode>(previewKind ? "preview" : "code")

  // Reset mode whenever the file changes — pick the most useful default for
  // the new file type, but never default to diff (only show diff if the user
  // explicitly clicks it).
  useEffect(() => {
    if (!selectedPath) return
    setMode(previewKind ? "preview" : "code")
  }, [selectedPath, previewKind])

  if (!selectedPath) {
    return (
      <div className="flex flex-1 items-center justify-center bg-background px-6 text-center text-sm text-muted-foreground">
        {isWaiting ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2Icon className="size-5 animate-spin" />
            <p>Loading workspace…</p>
          </div>
        ) : (
          <p>Select a file from the explorer to view its contents.</p>
        )}
      </div>
    )
  }

  const showDiff = isChanged && originalContent !== null && currentContent !== null
  // Coerce away invalid modes (e.g. "diff" when there's no diff to show, or
  // "preview" when the previous file had a preview but this one doesn't).
  const effectiveMode: Mode =
    mode === "diff" && !showDiff ? "code" : mode === "preview" && !previewKind ? "code" : mode

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <div className="flex items-center border-b bg-muted/30">
        <div className="flex items-center gap-1 px-1">
          {previewKind ? (
            <TabButton active={effectiveMode === "preview"} onClick={() => setMode("preview")}>
              <EyeIcon className="size-3.5" />
              <span>Preview</span>
            </TabButton>
          ) : null}
          <TabButton active={effectiveMode === "code"} onClick={() => setMode("code")}>
            {previewKind ? (
              <CodeIcon className="size-3.5" />
            ) : (
              <WorkspaceFileIcon name={name} type="file" />
            )}
            <span>{previewKind ? "Source" : name}</span>
          </TabButton>
          {showDiff ? (
            <TabButton
              active={effectiveMode === "diff"}
              onClick={() => setMode("diff")}
              accent="amber"
            >
              <span className="size-1.5 rounded-full bg-amber-500" />
              <span>Diff</span>
            </TabButton>
          ) : null}
        </div>
        <div className="ml-auto flex items-center gap-3 px-3">
          {isChanged ? (
            <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
              Modified
            </span>
          ) : null}
          {previewKind ? (
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {previewKind === "html" ? "HTML" : "Markdown"}
            </span>
          ) : null}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto bg-background">
        {isLoading ? (
          <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
            <Loader2Icon className="mr-2 size-4 animate-spin" /> Loading file…
          </div>
        ) : effectiveMode === "diff" ? (
          <DiffView original={originalContent ?? ""} current={currentContent ?? ""} />
        ) : effectiveMode === "preview" && previewKind === "html" ? (
          <HtmlPreview content={currentContent ?? ""} title={name} />
        ) : effectiveMode === "preview" && previewKind === "markdown" ? (
          <MarkdownPreview content={currentContent ?? ""} />
        ) : (
          <CodeView content={currentContent ?? ""} />
        )}
      </div>
    </div>
  )
}

function TabButton({
  active,
  onClick,
  accent = "blue",
  children,
}: {
  active: boolean
  onClick: () => void
  accent?: "blue" | "amber"
  children: React.ReactNode
}) {
  const accentClass =
    accent === "amber" ? "border-amber-500 dark:border-amber-400" : "border-primary"
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors",
        active
          ? cn("border-b-2 text-foreground", accentClass)
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

function CodeView({ content }: { content: string }) {
  return (
    <pre className="m-0 min-h-full overflow-auto whitespace-pre bg-background px-4 py-3 font-mono text-xs leading-5 text-foreground">
      {content || <span className="text-muted-foreground">(empty file)</span>}
    </pre>
  )
}

function MarkdownPreview({ content }: { content: string }) {
  if (!content.trim()) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        (empty markdown file)
      </div>
    )
  }
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none px-6 py-4">
      <MessageResponse>{content}</MessageResponse>
    </div>
  )
}

function HtmlPreview({ content, title }: { content: string; title: string }) {
  if (!content.trim()) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        (empty html file)
      </div>
    )
  }
  // `srcDoc` runs the HTML in an isolated browsing context. The sandbox keeps
  // it locked down: scripts run for fidelity, but it cannot reach our origin,
  // top-level navigation, or storage. Drop "allow-scripts" if you want fully
  // inert previews.
  return (
    <iframe
      key={content.length /* force reload when size changes */}
      title={`Preview of ${title}`}
      srcDoc={content}
      sandbox="allow-scripts allow-same-origin"
      className="size-full border-0 bg-white"
    />
  )
}

type DiffLine =
  | { kind: "context"; text: string }
  | { kind: "add"; text: string }
  | { kind: "remove"; text: string }

function DiffView({ original, current }: { original: string; current: string }) {
  const lines = useMemo(() => computeLineDiff(original, current), [original, current])
  return (
    <div className="min-h-full overflow-auto bg-background font-mono text-xs leading-5">
      {lines.map((line, idx) => (
        <div
          key={idx}
          className={cn(
            "flex items-start gap-2 px-4",
            line.kind === "add" && "bg-green-500/10 text-green-700 dark:text-green-300",
            line.kind === "remove" && "bg-red-500/10 text-red-700 dark:text-red-300",
          )}
        >
          <span className="w-4 select-none text-muted-foreground">
            {line.kind === "add" ? "+" : line.kind === "remove" ? "-" : " "}
          </span>
          <span className="whitespace-pre">{line.text || " "}</span>
        </div>
      ))}
    </div>
  )
}

/**
 * Tiny LCS line diff. Good enough for short files; we keep this dependency-free
 * so we don't pull in a diff library. For very large files we degrade to
 * showing the new content with a "modified" badge.
 */
function computeLineDiff(original: string, current: string): DiffLine[] {
  const a = original.split("\n")
  const b = current.split("\n")
  const MAX = 4000
  if (a.length > MAX || b.length > MAX) {
    return b.map(text => ({ kind: "context", text }))
  }

  const m = a.length
  const n = b.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      out.push({ kind: "context", text: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ kind: "remove", text: a[i] })
      i++
    } else {
      out.push({ kind: "add", text: b[j] })
      j++
    }
  }
  while (i < m) out.push({ kind: "remove", text: a[i++] })
  while (j < n) out.push({ kind: "add", text: b[j++] })
  return out
}
