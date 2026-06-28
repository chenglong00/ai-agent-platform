"use client"

import { memo, useEffect, useState } from "react"
import { ChevronRightIcon, Loader2Icon, WrenchIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ToolCallInfo } from "@/lib/chat"
import { CodeBlock } from "@/components/ai/code-block"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"

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

function formatToolName(name: string): string {
  return name.replace(/_/g, " ")
}

function formatArgsInline(args: Record<string, unknown>): string {
  const entries = Object.entries(args)
  if (entries.length === 0) return ""
  return entries.map(([k, v]) => `${k}: ${String(v)}`).join(" · ")
}

function StatusDot({ status }: { status: ToolCallInfo["status"] }) {
  if (status === "running") {
    return <Loader2Icon className="size-3 shrink-0 animate-spin text-primary" />
  }
  if (status === "error") {
    return <span className="size-1.5 shrink-0 rounded-full bg-destructive" />
  }
  return <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
}

type ToolCallCardProps = {
  toolCall: ToolCallInfo
  className?: string
}

export const ToolCallCard = memo(({ toolCall, className }: ToolCallCardProps) => {
  const isRunning = toolCall.status === "running"
  const [open, setOpen] = useState(isRunning)
  const elapsed = getElapsedTime(toolCall.started_at, toolCall.completed_at)
  const argsInline = formatArgsInline(toolCall.args)
  const resultPreview =
    toolCall.result != null ? String(toolCall.result).replace(/\s+/g, " ").trim() : ""

  useEffect(() => {
    if (isRunning) setOpen(true)
  }, [isRunning])

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={cn("rounded-md border border-border/60 bg-muted/20", className)}
    >
      <CollapsibleTrigger className="group flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs hover:bg-muted/40">
        <ChevronRightIcon
          className={cn(
            "size-3 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
        />
        <StatusDot status={toolCall.status} />
        <WrenchIcon className="size-3 shrink-0 text-muted-foreground" />
        <span className="shrink-0 font-medium capitalize">{formatToolName(toolCall.tool_name)}</span>
        {argsInline ? (
          <span className="min-w-0 truncate text-muted-foreground">{argsInline}</span>
        ) : null}
        {elapsed ? (
          <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">{elapsed}</span>
        ) : null}
        {!open && resultPreview && !isRunning ? (
          <span className="min-w-0 max-w-[40%] truncate text-muted-foreground">
            {resultPreview}
          </span>
        ) : null}
      </CollapsibleTrigger>

      <CollapsibleContent className="border-t border-border/50 px-2.5 py-2 text-xs">
        {Object.keys(toolCall.args).length > 0 && (
          <div className="mb-2">
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Input
            </p>
            <CodeBlock
              code={JSON.stringify(toolCall.args, null, 2)}
              language="json"
              className="text-[11px]"
            />
          </div>
        )}
        {toolCall.result !== undefined ? (
          <div>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Result
            </p>
            <p className="whitespace-pre-wrap text-foreground/90">{toolCall.result}</p>
          </div>
        ) : isRunning ? (
          <p className="text-muted-foreground">Running…</p>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  )
})

ToolCallCard.displayName = "ToolCallCard"

type ToolCallProgressProps = {
  toolCalls: ToolCallInfo[]
  className?: string
}

export const ToolCallProgress = memo(({ toolCalls, className }: ToolCallProgressProps) => {
  const anyRunning = toolCalls.some(t => t.status === "running")
  const completed = toolCalls.filter(t => t.status === "complete" || t.status === "error").length
  const [groupOpen, setGroupOpen] = useState(anyRunning || toolCalls.length <= 2)

  useEffect(() => {
    if (anyRunning) setGroupOpen(true)
  }, [anyRunning])

  if (toolCalls.length === 0) return null

  if (toolCalls.length === 1) {
    return <ToolCallCard toolCall={toolCalls[0]!} className={className} />
  }

  const summary = `${toolCalls.length} tools`

  return (
    <Collapsible
      open={groupOpen}
      onOpenChange={setGroupOpen}
      className={cn("rounded-md border border-border/60 bg-muted/10", className)}
    >
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted/30">
        <ChevronRightIcon
          className={cn(
            "size-3 shrink-0 transition-transform",
            groupOpen && "rotate-90",
          )}
        />
        <WrenchIcon className="size-3 shrink-0" />
        <span className="font-medium text-foreground">{summary}</span>
        <span className="truncate">
          {completed}/{toolCalls.length} done
        </span>
        {anyRunning ? (
          <Loader2Icon className="ml-auto size-3 shrink-0 animate-spin text-primary" />
        ) : null}
      </CollapsibleTrigger>

      <CollapsibleContent className="space-y-1 border-t border-border/50 p-1.5">
        {toolCalls.map(t => (
          <ToolCallCard key={t.id} toolCall={t} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
})

ToolCallProgress.displayName = "ToolCallProgress"
