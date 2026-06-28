"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Loader2Icon, SendHorizonalIcon } from "lucide-react"
import { flushSync } from "react-dom"

import { BrowserLivePanel } from "@/components/ai/browser-live-panel"
import { Message, MessageContent, MessageResponse } from "@/components/ai/message"
import {
  AssistantTurnContent,
  parseMessageBlocks,
} from "@/components/ai/message-blocks"
import { SubagentProgress, SynthesisIndicator } from "@/components/ai/subagent-card"
import { ToolCallProgress } from "@/components/ai/tool-call-card"
import { TodoList } from "@/components/ai/todo-list"
import { ContextMentionMenuPortal } from "@/components/ai/context-mention-menu"
import { SkillSlashMenuPortal } from "@/components/ai/skill-slash-menu"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useContextMentionMenu } from "@/hooks/use-context-mention-menu"
import { useSkillSlashMenu } from "@/hooks/use-skill-slash-menu"
import { getToken } from "@/lib/auth"
import {
  createChatConversation,
  fetchChatMessages,
  notifyChatConversationsUpdated,
  streamChatMessage,
  workspaceConversationStorageKey,
  type ChatMessageDto,
  type MessageBlockDto,
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
  /** Workspace root label from the API. */
  workspaceRoot?: string | null
  /** File currently open in the editor. */
  selectedPath?: string | null
  className?: string
}

type WorkspaceChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
  content_format: "markdown" | "plain"
  pending?: boolean
  subagents?: SubagentInfo[]
  toolCalls?: ToolCallInfo[]
  todos?: TodoItem[]
  blocks?: MessageBlockDto[]
  interrupted?: boolean
}

function makeId(prefix: string): string {
  if (typeof globalThis !== "undefined" && globalThis.crypto?.randomUUID) {
    return `${prefix}:${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}:${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function hasBrowserToolCalls(toolCalls?: ToolCallInfo[]): boolean {
  return !!toolCalls?.some(t => t.tool_name.startsWith("browser_"))
}

function rowToMessage(m: ChatMessageDto): WorkspaceChatMessage {
  const parsed = parseMessageBlocks(m.blocks)
  return {
    id: m.id,
    role: m.role,
    text: m.text || parsed.text,
    content_format:
      m.content_format ??
      parsed.content_format ??
      (m.role === "assistant" ? "markdown" : "plain"),
    blocks: m.blocks,
    toolCalls: parsed.toolCalls.length ? parsed.toolCalls : undefined,
    subagents: parsed.subagents.length ? parsed.subagents : undefined,
    todos: parsed.todos.length ? parsed.todos : undefined,
  }
}

export function WorkspaceChatPanel({
  onTurnComplete,
  workspaceRoot,
  selectedPath,
  className,
}: WorkspaceChatPanelProps) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<WorkspaceChatMessage[]>([])
  const [sessionReady, setSessionReady] = useState(false)
  const [text, setText] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const slash = useSkillSlashMenu({ value: text, onValueChange: setText })
  const context = useContextMentionMenu({ value: text, onValueChange: setText })
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [authToken, setAuthToken] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  })

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      const token = getToken()
      if (!token) {
        setSessionReady(true)
        return
      }
      setAuthToken(token)

      const storedId = localStorage.getItem(workspaceConversationStorageKey)
      if (!storedId) {
        setSessionReady(true)
        return
      }

      try {
        const rows = await fetchChatMessages(token, storedId)
        if (cancelled) return
        setConversationId(storedId)
        setMessages(rows.map(rowToMessage))
      } catch {
        if (!cancelled) {
          localStorage.removeItem(workspaceConversationStorageKey)
        }
      } finally {
        if (!cancelled) setSessionReady(true)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

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
            name: "Workspace",
            description: "Agent session from workspace page",
          })
          conv = created.id
          localStorage.setItem(workspaceConversationStorageKey, conv)
          setConversationId(conv)
          notifyChatConversationsUpdated()
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
        { id: tempUser, role: "user", text: trimmed, content_format: "plain" },
        {
          id: tempAssistant,
          role: "assistant",
          text: "",
          content_format: "markdown",
          pending: true,
          toolCalls: [],
          subagents: [],
          todos: [],
        },
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
        for await (const event of streamChatMessage(token, conv, trimmed, {
          context: "workspace",
          workspaceRoot: workspaceRoot ?? undefined,
          workspaceSelectedPath: selectedPath ?? undefined,
        })) {
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
            })
            flushSync(() => flushSubagents())
          } else if (event.type === "subagent_token") {
            const sa = subagentMap.get(event.id)
            if (sa) {
              subagentMap.set(event.id, {
                ...sa,
                content: sa.content + event.content,
              })
            }
            flushSubagents()
          } else if (event.type === "subagent_done") {
            const sa = subagentMap.get(event.id)
            if (sa) {
              subagentMap.set(event.id, {
                ...sa,
                status: event.status,
                result: event.result,
                completed_at: event.completed_at,
              })
            }
            flushSubagents()
          } else if (event.type === "tool_call_start") {
            toolCallMap.set(event.id, {
              id: event.id,
              tool_name: event.tool_name,
              args: event.args,
              status: "running",
              started_at: event.started_at,
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
          } else if (event.type === "browser_preview") {
            const tc = toolCallMap.get(event.tool_call_id)
            if (tc) {
              toolCallMap.set(event.tool_call_id, {
                ...tc,
                previewImageBase64: event.image_base64,
                previewUrl: event.url,
              })
            }
            flushSync(() => flushToolCalls())
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
              prev.map(m => {
                if (m.id === tempUser) return m
                if (m.id === tempAssistant) {
                  return {
                    ...m,
                    id: event.assistant_message_id,
                    text: event.assistant_text,
                    blocks: event.assistant_blocks,
                    pending: false,
                    interrupted: event.interrupted,
                    subagents: event.assistant_blocks
                      ? undefined
                      : Array.from(subagentMap.values()),
                    toolCalls: event.assistant_blocks
                      ? undefined
                      : Array.from(toolCallMap.values()),
                  }
                }
                return m
              }),
            )
            notifyChatConversationsUpdated()
          } else if (event.type === "error") {
            setError(event.message)
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Stream failed")
        setMessages(prev =>
          prev.filter(m => m.id !== tempUser && m.id !== tempAssistant),
        )
      } finally {
        setSending(false)
        onTurnComplete?.()
      }
    },
    [conversationId, sending, onTurnComplete, workspaceRoot, selectedPath],
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void sendPrompt(text)
    setText("")
  }

  const isEmpty = messages.length === 0

  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col bg-sidebar text-sidebar-foreground",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <span>Deep Agent</span>
        {sending ? (
          <span className="flex items-center gap-1 normal-case font-normal">
            <Loader2Icon className="size-3 animate-spin" />
            Working…
          </span>
        ) : null}
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {!sessionReady ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2Icon className="size-3 animate-spin" />
            Loading agent…
          </div>
        ) : null}

        {error ? (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
            {error}
          </div>
        ) : null}

        {sessionReady && isEmpty ? (
          <div className="space-y-3">
            <p className="text-xs leading-relaxed text-muted-foreground">
              The deep agent shares your sandbox workspace. Ask it to create or
              modify files — changes appear in the file tree after each turn.
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

        {messages.map(msg => {
          if (msg.role === "user") {
            return (
              <div key={msg.id} className="flex justify-end">
                <div className="max-w-[85%] rounded-lg rounded-br-sm bg-primary px-3 py-2 text-xs leading-relaxed text-primary-foreground">
                  {msg.text}
                </div>
              </div>
            )
          }

          const hasSubagents = !!msg.subagents?.length
          const hasToolCalls = !!msg.toolCalls?.length
          const hasTodos = !!msg.todos?.length
          const allDone =
            hasSubagents &&
            msg.subagents!.every(
              s => s.status === "complete" || s.status === "error",
            )
          const isActiveTurn = !!msg.pending && sending
          const usePersistedBlocks = !msg.pending && !!msg.blocks?.length
          const showThinking =
            isActiveTurn && !msg.text && !hasSubagents && !hasToolCalls && !hasTodos

          if (usePersistedBlocks) {
            return (
              <div key={msg.id}>
                <AssistantTurnContent
                  blocks={msg.blocks}
                  interrupted={msg.interrupted}
                />
              </div>
            )
          }

          return (
            <div key={msg.id} className="space-y-1.5">
              {showThinking && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2Icon className="size-3 animate-spin" />
                  Thinking…
                </div>
              )}
              {(hasTodos || (isActiveTurn && hasSubagents)) && (
                <TodoList
                  todos={msg.todos ?? []}
                  isLoading={isActiveTurn && !hasTodos}
                />
              )}
              {isActiveTurn && hasBrowserToolCalls(msg.toolCalls) && authToken && (
                <BrowserLivePanel accessToken={authToken} className="text-foreground" />
              )}
              {hasToolCalls && <ToolCallProgress toolCalls={msg.toolCalls!} />}
              {hasSubagents && <SubagentProgress subagents={msg.subagents!} />}
              {hasSubagents && allDone && isActiveTurn && (
                <SynthesisIndicator
                  subagents={msg.subagents!}
                  isStreaming
                  className="mb-1"
                />
              )}
              {msg.text ? (
                <Message from="assistant">
                  <MessageContent>
                    <MessageResponse>{msg.text}</MessageResponse>
                    {msg.interrupted ? (
                      <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-400">
                        ⏸ Waiting for approval — reply <strong>yes</strong> or{" "}
                        <strong>no</strong>.
                      </p>
                    ) : null}
                  </MessageContent>
                </Message>
              ) : null}
            </div>
          )
        })}
      </div>

      <form onSubmit={handleSubmit} className="border-t px-3 py-2">
        <div className="flex items-end gap-2">
          <div className="relative min-w-0 flex-1">
            <ContextMentionMenuPortal
              open={context.menuOpen}
              anchorRef={textareaRef}
              items={context.filteredItems}
              selectedIndex={context.selectedIndex}
              onSelect={context.selectItem}
              loading={context.loading}
            />
            <SkillSlashMenuPortal
              open={slash.menuOpen && !context.menuOpen}
              anchorRef={textareaRef}
              skills={slash.filteredSkills}
              selectedIndex={slash.selectedIndex}
              onSelect={slash.selectSkill}
              loading={slash.skillsLoading}
            />
            <Textarea
              ref={textareaRef}
              value={text}
              onChange={e => {
                setText(e.target.value)
                slash.textareaRef.current = e.currentTarget
                context.textareaRef.current = e.currentTarget
                slash.onTextareaChange(e)
                context.onTextareaChange(e)
              }}
              placeholder="Ask the agent… (/ skills, @ context)"
              disabled={sending || !sessionReady}
              rows={2}
              onSelect={e => {
                slash.textareaRef.current = e.currentTarget
                context.textareaRef.current = e.currentTarget
                slash.onTextareaSelect(e)
                context.onTextareaSelect(e)
              }}
              onClick={e => {
                slash.textareaRef.current = e.currentTarget
                context.textareaRef.current = e.currentTarget
                slash.onTextareaSelect(e)
                context.onTextareaSelect(e)
              }}
              onKeyDown={e => {
                slash.textareaRef.current = e.currentTarget
                context.textareaRef.current = e.currentTarget
                if (context.onTextareaKeyDown(e)) return
                if (slash.onTextareaKeyDown(e)) return
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  void sendPrompt(text)
                  setText("")
                }
              }}
              className="min-h-[42px] resize-none text-xs"
            />
          </div>
          <Button
            type="submit"
            size="icon"
            disabled={sending || !sessionReady || !text.trim()}
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
