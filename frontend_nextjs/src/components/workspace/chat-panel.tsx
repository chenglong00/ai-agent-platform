"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Loader2Icon, SendHorizonalIcon } from "lucide-react"
import { flushSync } from "react-dom"

import { MessageResponse } from "@/components/ai/message"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { getToken } from "@/lib/auth"
import {
  createChatConversation,
  streamChatMessage,
  type SubagentInfo,
  type TodoItem,
  type ToolCallInfo,
} from "@/lib/chat"
import { cn } from "@/lib/utils"

const EXAMPLE_PROMPTS = [
  "Create an `index.html` for a hello-world site under a new `hello/` folder.",
  "Read `index.html` and give me a one-paragraph summary of what it contains.",
  "List every file in the workspace and tell me the total file count.",
  "Add a `README.md` with a short description of this workspace.",
]

type WorkspaceChatPanelProps = {
  /** Called once per assistant turn after streaming finishes. */
  onTurnComplete?: () => void
  className?: string
}

type WorkspaceChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
  pending?: boolean
  subagents?: SubagentInfo[]
  toolCalls?: ToolCallInfo[]
  todos?: TodoItem[]
  interrupted?: boolean
}

function makeId(prefix: string): string {
  if (typeof globalThis !== "undefined" && globalThis.crypto?.randomUUID) {
    return `${prefix}:${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}:${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function WorkspaceChatPanel({
  onTurnComplete,
  className,
}: WorkspaceChatPanelProps) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<WorkspaceChatMessage[]>([])
  const [text, setText] = useState("")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on every render so streamed text stays pinned to the bottom.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  })

  const sendPrompt = useCallback(
    async (raw: string) => {
      const trimmed = raw.trim()
      if (!trimmed || sending) return
      const token = getToken()
      if (!token) {
        setError("Not signed in.")
        return
      }

      let conv = conversationId
      if (!conv) {
        try {
          const created = await createChatConversation(token, {
            name: "Workspace session",
            description: "Created from workspace page",
          })
          conv = created.id
          setConversationId(conv)
        } catch (e) {
          setError(e instanceof Error ? e.message : "Could not start conversation")
          return
        }
      }

      const tempUser = makeId("u")
      const tempAssistant = makeId("a")

      setSending(true)
      setError(null)
      setMessages(prev => [
        ...prev,
        { id: tempUser, role: "user", text: trimmed },
        { id: tempAssistant, role: "assistant", text: "", pending: true, toolCalls: [] },
      ])

      const subagentMap = new Map<string, SubagentInfo>()
      const toolCallMap = new Map<string, ToolCallInfo>()
      const flushSubagents = () =>
        setMessages(prev =>
          prev.map(m =>
            m.id === tempAssistant
              ? { ...m, subagents: Array.from(subagentMap.values()) }
              : m,
          ),
        )
      const flushToolCalls = () =>
        setMessages(prev =>
          prev.map(m =>
            m.id === tempAssistant
              ? { ...m, toolCalls: Array.from(toolCallMap.values()) }
              : m,
          ),
        )

      try {
        for await (const event of streamChatMessage(token, conv, trimmed)) {
          if (event.type === "token") {
            setMessages(prev =>
              prev.map(m =>
                m.id === tempAssistant
                  ? { ...m, text: m.text + event.content, pending: false }
                  : m,
              ),
            )
          } else if (event.type === "subagent_start") {
            subagentMap.set(event.id, {
              id: event.id,
              subagent_type: event.subagent_type,
              description: event.description,
              status: "running",
              content: "",
              started_at: event.started_at,
              result: undefined,
              completed_at: undefined,
            })
            flushSync(() => flushSubagents())
          } else if (event.type === "subagent_token") {
            const sa = subagentMap.get(event.id)
            if (sa)
              subagentMap.set(event.id, {
                ...sa,
                content: sa.content + event.content,
              })
            flushSubagents()
          } else if (event.type === "subagent_done") {
            const sa = subagentMap.get(event.id)
            if (sa)
              subagentMap.set(event.id, {
                ...sa,
                status: event.status,
                result: event.result,
                completed_at: event.completed_at,
              })
            flushSubagents()
          } else if (event.type === "tool_call_start") {
            toolCallMap.set(event.id, {
              id: event.id,
              tool_name: event.tool_name,
              args: event.args,
              status: "running",
              result: undefined,
              started_at: event.started_at,
              completed_at: undefined,
            })
            flushSync(() => flushToolCalls())
          } else if (event.type === "tool_call_end") {
            const tc = toolCallMap.get(event.id)
            if (tc) {
              toolCallMap.set(event.id, {
                ...tc,
                status: event.status,
                result: event.result,
                completed_at: event.completed_at,
              })
            }
            flushToolCalls()
          } else if (event.type === "todos_update") {
            flushSync(() =>
              setMessages(prev =>
                prev.map(m =>
                  m.id === tempAssistant ? { ...m, todos: event.todos } : m,
                ),
              ),
            )
          } else if (event.type === "saved") {
            setMessages(prev =>
              prev.map(m =>
                m.id === tempAssistant
                  ? {
                      ...m,
                      id: event.assistant_message_id,
                      text: event.assistant_text,
                      pending: false,
                      interrupted: event.interrupted,
                      toolCalls: Array.from(toolCallMap.values()),
                    }
                  : m,
              ),
            )
          } else if (event.type === "error") {
            setError(event.message)
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Stream failed")
      } finally {
        setSending(false)
        onTurnComplete?.()
      }
    },
    [conversationId, sending, onTurnComplete],
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void sendPrompt(text)
    setText("")
  }

  const isEmpty = messages.length === 0

  return (
    <div className={cn("flex h-full min-h-0 flex-col bg-sidebar text-sidebar-foreground", className)}>
      <div className="flex items-center justify-between border-b px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <span>Agent</span>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {error ? (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
            {error}
          </div>
        ) : null}

        {isEmpty ? (
          <div className="space-y-3">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Ask the agent to create or modify files in this workspace. Try one of these:
            </p>
            <div className="space-y-1.5">
              {EXAMPLE_PROMPTS.map(prompt => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void sendPrompt(prompt)}
                  disabled={sending}
                  className="w-full rounded border px-2.5 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground disabled:opacity-40"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map(msg =>
          msg.role === "user" ? (
            <div key={msg.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-lg rounded-br-sm bg-primary px-3 py-2 text-xs leading-relaxed text-primary-foreground">
                {msg.text}
              </div>
            </div>
          ) : (
            <div key={msg.id} className="space-y-1.5">
              {msg.toolCalls && msg.toolCalls.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {msg.toolCalls.map(tc => (
                    <span
                      key={tc.id}
                      className={cn(
                        "inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-[10px]",
                        tc.status === "complete"
                          ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                          : "bg-amber-500/10 text-amber-700 dark:text-amber-300",
                      )}
                    >
                      {tc.status === "complete" ? "✓" : "⟳"} {tc.tool_name}
                    </span>
                  ))}
                </div>
              ) : null}
              {msg.subagents && msg.subagents.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {msg.subagents.map(sa => (
                    <span
                      key={sa.id}
                      className={cn(
                        "inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-[10px]",
                        sa.status === "complete"
                          ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                          : "bg-blue-500/10 text-blue-700 dark:text-blue-300",
                      )}
                    >
                      {sa.status === "complete" ? "✓" : "⟳"} {sa.subagent_type}
                    </span>
                  ))}
                </div>
              ) : null}
              {msg.text ? (
                <div className="rounded border bg-background px-3 py-2 text-xs leading-relaxed text-foreground">
                  <MessageResponse>{msg.text}</MessageResponse>
                  {msg.interrupted ? (
                    <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-400">
                      ⏸ Waiting for approval — reply <strong>yes</strong> or <strong>no</strong>.
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ),
        )}

        {sending ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2Icon className="size-3 animate-spin" /> Working…
          </div>
        ) : null}
      </div>

      <form onSubmit={handleSubmit} className="border-t px-3 py-2">
        <div className="flex items-end gap-2">
          <Textarea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Ask the agent to modify files…"
            disabled={sending}
            rows={2}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                void sendPrompt(text)
                setText("")
              }
            }}
            className="min-h-[42px] resize-none text-xs"
          />
          <Button
            type="submit"
            size="icon"
            disabled={sending || !text.trim()}
            aria-label="Send message"
          >
            {sending ? (
              <Loader2Icon className="size-4 animate-spin" />
            ) : (
              <SendHorizonalIcon className="size-4" />
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
