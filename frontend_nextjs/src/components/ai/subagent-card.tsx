"use client"

import { memo, useState } from "react"
import { cn } from "@/lib/utils"
import type { SubagentInfo } from "@/lib/chat"

// ── Helpers ───────────────────────────────────────────────────────────────────

function getElapsedTime(
  startedAt: number | undefined,
  completedAt: number | undefined,
): string | null {
  if (!startedAt) return null
  const end = completedAt ?? Date.now()
  const seconds = Math.round((end - startedAt) / 1000)
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

// ── Status icons ──────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: SubagentInfo["status"] }) {
  switch (status) {
    case "pending":
      return <span className="text-muted-foreground">○</span>
    case "running":
      return <span className="animate-spin text-primary inline-block">◉</span>
    case "complete":
      return <span className="text-green-500">✓</span>
    case "error":
      return <span className="text-destructive">✕</span>
  }
}

function StatusBadge({ status }: { status: SubagentInfo["status"] }) {
  const styles: Record<SubagentInfo["status"], string> = {
    pending: "bg-muted text-muted-foreground",
    running: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    complete: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
    error: "bg-destructive/10 text-destructive",
  }

  return (
    <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", styles[status])}>
      {status}
    </span>
  )
}

// ── SubagentCard ──────────────────────────────────────────────────────────────

type CardProps = {
  subagent: SubagentInfo
  className?: string
}

export const SubagentCard = memo(({ subagent, className }: CardProps) => {
  const [expanded, setExpanded] = useState(true)

  const title = subagent.subagent_type || `Agent ${subagent.id.slice(0, 8)}`
  const description = subagent.description

  const displayContent =
    subagent.status === "complete" ? subagent.result : subagent.content

  const elapsed = getElapsedTime(subagent.started_at, subagent.completed_at)

  return (
    <div className={cn("rounded-lg border bg-card shadow-sm", className)}>
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <StatusIcon status={subagent.status} />
          <div className="min-w-0">
            <h4 className="font-semibold text-sm capitalize truncate">{title}</h4>
            {description && (
              <p className="text-xs text-muted-foreground truncate">{description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-3">
          {elapsed && <span className="text-xs text-muted-foreground">{elapsed}</span>}
          <StatusBadge status={subagent.status} />
        </div>
      </button>

      {expanded && displayContent && (
        <div className="border-t px-4 py-3">
          <div className="prose prose-sm dark:prose-invert max-w-none line-clamp-6 text-sm">
            {displayContent}
            {subagent.status === "running" && (
              <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-primary" />
            )}
          </div>
        </div>
      )}
    </div>
  )
})

SubagentCard.displayName = "SubagentCard"

// ── SubagentProgress ──────────────────────────────────────────────────────────

type ProgressProps = {
  subagents: SubagentInfo[]
  className?: string
}

export const SubagentProgress = memo(({ subagents, className }: ProgressProps) => {
  if (subagents.length === 0) return null
  const completed = subagents.filter(s => s.status === "complete").length
  const total = subagents.length
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <div className={cn("space-y-3 border-l-2 border-primary/20 pl-4 ml-1", className)}>
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-medium">Specialist agents</span>
          <span>{completed}/{total} complete</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
      <div className="space-y-2">
        {subagents.map(s => (
          <SubagentCard key={s.id} subagent={s} />
        ))}
      </div>
    </div>
  )
})

SubagentProgress.displayName = "SubagentProgress"

// ── SynthesisIndicator ────────────────────────────────────────────────────────

type SynthesisProps = {
  subagents: SubagentInfo[]
  isStreaming: boolean
  className?: string
}

export const SynthesisIndicator = memo(({ subagents, isStreaming, className }: SynthesisProps) => {
  const allDone =
    subagents.length > 0 &&
    subagents.every(s => s.status === "complete" || s.status === "error")

  if (!allDone || !isStreaming) return null

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg bg-purple-50 dark:bg-purple-950/30 px-4 py-2 text-sm text-purple-700 dark:text-purple-300",
        className,
      )}
    >
      <span className="inline-block animate-spin">⟳</span>
      Synthesizing results from {subagents.length} subagent
      {subagents.length !== 1 ? "s" : ""}…
    </div>
  )
})

SynthesisIndicator.displayName = "SynthesisIndicator"
