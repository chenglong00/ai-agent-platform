"use client"

import { memo } from "react"
import { Message, MessageContent, MessageResponse } from "@/components/ai/message"
import { SubagentProgress } from "@/components/ai/subagent-card"
import { ToolCallProgress } from "@/components/ai/tool-call-card"
import { TodoList } from "@/components/ai/todo-list"
import { CodeBlock } from "@/components/ai/code-block"
import type { MessageBlockDto } from "@/lib/chat"
import type { SubagentInfo, TodoItem, ToolCallInfo } from "@/lib/chat"
import { cn } from "@/lib/utils"

export type ParsedMessageBlocks = {
  text: string
  content_format: "markdown" | "plain"
  toolCalls: ToolCallInfo[]
  subagents: SubagentInfo[]
  todos: TodoItem[]
  otherBlocks: MessageBlockDto[]
}

export function parseMessageBlocks(blocks?: MessageBlockDto[]): ParsedMessageBlocks {
  const textParts: string[] = []
  let content_format: "markdown" | "plain" = "plain"
  const toolCalls: ToolCallInfo[] = []
  const subagents: SubagentInfo[] = []
  let todos: TodoItem[] = []
  const otherBlocks: MessageBlockDto[] = []

  for (const block of [...(blocks ?? [])].sort((a, b) => a.position - b.position)) {
    const p = block.payload
    switch (block.type) {
      case "text": {
        const t = String(p.text ?? "")
        if (t) textParts.push(t)
        if (p.format === "markdown") content_format = "markdown"
        else if (p.format === "plain") content_format = "plain"
        break
      }
      case "tool_call":
        toolCalls.push({
          id: String(p.id ?? ""),
          tool_name: String(p.tool_name ?? ""),
          args: (p.args as Record<string, unknown>) ?? {},
          status: (p.status as ToolCallInfo["status"]) ?? "complete",
          result: p.result != null ? String(p.result) : undefined,
          started_at: typeof p.started_at === "number" ? p.started_at : undefined,
          completed_at: typeof p.completed_at === "number" ? p.completed_at : undefined,
        })
        break
      case "subagent":
        subagents.push({
          id: String(p.id ?? ""),
          subagent_type: String(p.subagent_type ?? "agent"),
          description: String(p.description ?? ""),
          status: (p.status as SubagentInfo["status"]) ?? "complete",
          content: String(p.content ?? ""),
          result: p.result != null ? String(p.result) : undefined,
          started_at: typeof p.started_at === "number" ? p.started_at : undefined,
          completed_at: typeof p.completed_at === "number" ? p.completed_at : undefined,
        })
        break
      case "todo_list":
        todos = Array.isArray(p.todos)
          ? (p.todos as TodoItem[])
          : []
        break
      default:
        otherBlocks.push(block)
    }
  }

  return {
    text: textParts.join("\n"),
    content_format,
    toolCalls,
    subagents,
    todos,
    otherBlocks,
  }
}

type MessageBlocksProps = {
  blocks?: MessageBlockDto[]
  className?: string
}

function TableBlock({ payload }: { payload: Record<string, unknown> }) {
  const headers = Array.isArray(payload.headers) ? (payload.headers as string[]) : []
  const rows = Array.isArray(payload.rows) ? (payload.rows as string[][]) : []
  if (!headers.length && !rows.length) return null
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        {headers.length > 0 && (
          <thead className="bg-muted/50">
            <tr>
              {headers.map(h => (
                <th key={h} className="px-3 py-2 text-left font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function OtherBlock({ block }: { block: MessageBlockDto }) {
  const p = block.payload
  switch (block.type) {
    case "code":
      return (
        <CodeBlock
          code={String(p.source ?? "")}
          language={String(p.language ?? "text")}
        />
      )
    case "table":
      return <TableBlock payload={p} />
    case "link": {
      const url = String(p.url ?? "")
      const label = String(p.label ?? url)
      if (!url) return null
      return (
        <a href={url} className="text-primary underline" target="_blank" rel="noreferrer">
          {label}
        </a>
      )
    }
    case "chart":
      return (
        <pre className="rounded-md bg-muted/50 p-3 text-xs overflow-x-auto">
          {JSON.stringify(p, null, 2)}
        </pre>
      )
    default:
      return (
        <pre className="rounded-md bg-muted/50 p-3 text-xs overflow-x-auto">
          {JSON.stringify(p, null, 2)}
        </pre>
      )
  }
}

type AssistantTurnContentProps = {
  blocks?: MessageBlockDto[]
  className?: string
  interrupted?: boolean
}

/** Renders a persisted assistant turn — progress blocks full-width, text in bubble. */
export const AssistantTurnContent = memo(
  ({ blocks, className, interrupted }: AssistantTurnContentProps) => {
    const parsed = parseMessageBlocks(blocks)
    const hasTodos = parsed.todos.length > 0
    const hasToolCalls = parsed.toolCalls.length > 0
    const hasSubagents = parsed.subagents.length > 0
    const hasOther = parsed.otherBlocks.length > 0
    const hasText = !!parsed.text

    if (!hasTodos && !hasToolCalls && !hasSubagents && !hasOther && !hasText) {
      return null
    }

    return (
      <div className={cn("space-y-2", className)}>
        {hasTodos && <TodoList todos={parsed.todos} className="mx-1" />}
        {hasToolCalls && (
          <div className="mb-2 space-y-2 px-1">
            <ToolCallProgress toolCalls={parsed.toolCalls} />
          </div>
        )}
        {hasSubagents && (
          <div className="mb-2 space-y-2 px-1">
            <SubagentProgress subagents={parsed.subagents} />
          </div>
        )}
        {parsed.otherBlocks.map((block, i) => (
          <OtherBlock key={`${block.type}-${block.position}-${i}`} block={block} />
        ))}
        {hasText && (
          <Message from="assistant">
            <MessageContent>
              {parsed.content_format === "markdown" ? (
                <MessageResponse>{parsed.text}</MessageResponse>
              ) : (
                <p className="whitespace-pre-wrap text-sm">{parsed.text}</p>
              )}
              {interrupted && (
                <p className="mt-2 text-sm text-amber-600">
                  ⏸ Waiting for your approval — reply <strong>yes</strong> or{" "}
                  <strong>no</strong>.
                </p>
              )}
            </MessageContent>
          </Message>
        )}
      </div>
    )
  },
)

AssistantTurnContent.displayName = "AssistantTurnContent"

/** Compact inline layout (e.g. previews). Prefer AssistantTurnContent in chat. */
export const MessageBlocks = memo(({ blocks, className }: MessageBlocksProps) => (
  <AssistantTurnContent blocks={blocks} className={className} />
))

MessageBlocks.displayName = "MessageBlocks"
