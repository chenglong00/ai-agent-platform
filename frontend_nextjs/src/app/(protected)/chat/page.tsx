"use client"

import { Loader2Icon, MessageCircleIcon } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import { flushSync } from "react-dom"
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai/conversation"
import { Message, MessageContent, MessageResponse } from "@/components/ai/message"
import {
  PromptInput,
  PromptInputAttachments,
  PromptInputAttachment,
  PromptInputBody,
  PromptInputFooter,
  PromptInputProvider,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  PromptInputActionMenu,
  PromptInputActionMenuTrigger,
  PromptInputActionMenuContent,
  PromptInputActionAddAttachments,
} from "@/components/ai/prompt-input"
import { AppSidebar } from "@/components/app-sidebar"
import { Input } from "@/components/ui/input"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import {
  chatConversationStorageKey,
  createChatConversation,
  fetchChatConversation,
  fetchChatMessages,
  notifyChatConversationsUpdated,
  streamChatMessage,
  updateChatConversation,
} from "@/lib/chat"
import { getToken } from "@/lib/auth"
import { cn } from "@/lib/utils"
import type { ChatMessageDto, MessageBlockDto, SubagentInfo, TodoItem, ToolCallInfo } from "@/lib/chat"
import { SubagentProgress, SynthesisIndicator } from "@/components/ai/subagent-card"
import { ToolCallProgress } from "@/components/ai/tool-call-card"
import { AssistantTurnContent, parseMessageBlocks } from "@/components/ai/message-blocks"
import { TodoList } from "@/components/ai/todo-list"

const CHAT_PATH = "/chat"

type ChatMessage = {
  id: string
  from: "user" | "assistant"
  text: string
  content_format: "markdown" | "plain"
  created_at?: string
  /** Assistant row shown while the stream is in progress. */
  pending?: boolean
  /** Subagents that ran during this assistant turn. */
  subagents?: SubagentInfo[]
  /** Direct tool calls during this assistant turn. */
  toolCalls?: ToolCallInfo[]
  /** Todo items tracked during this assistant turn. */
  todos?: TodoItem[]
  /** Persisted structured content (from API). */
  blocks?: MessageBlockDto[]
  interrupted?: boolean
}

const CHAT_CONVERSATION_ID_PARAM = "c"
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function rowToMessage(m: ChatMessageDto): ChatMessage {
  const parsed = parseMessageBlocks(m.blocks)
  return {
    id: m.id,
    from: m.role,
    text: m.text || parsed.text,
    created_at: m.created_at,
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

function makeTempId(prefix: string): string {
  if (typeof globalThis !== "undefined" && globalThis.crypto?.randomUUID) {
    return `${prefix}:${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}:${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function ChatPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [sessionReady, setSessionReady] = useState(false)
  const [initError, setInitError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [conversationTitle, setConversationTitle] = useState("")
  const [titleEditing, setTitleEditing] = useState(false)
  const [titleDraft, setTitleDraft] = useState("")
  const [titleSaving, setTitleSaving] = useState(false)
  const [titleError, setTitleError] = useState<string | null>(null)
  const prevConversationIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!conversationId) {
      setConversationTitle("New chat")
      prevConversationIdRef.current = null
      return
    }
    if (prevConversationIdRef.current !== conversationId) {
      setConversationTitle("")
      prevConversationIdRef.current = conversationId
    }
    let cancelled = false
    void (async () => {
      const token = getToken()
      if (!token) return
      try {
        const c = await fetchChatConversation(token, conversationId)
        if (!cancelled) setConversationTitle(c.name)
      } catch {
        if (!cancelled) setConversationTitle("Chat")
      }
    })()
    return () => {
      cancelled = true
    }
  }, [conversationId])

  useEffect(() => {
    setTitleEditing(false)
    setTitleDraft("")
    setTitleError(null)
  }, [conversationId])

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      const token = getToken()
      if (!token) {
        router.replace("/login")
        return
      }

      if (searchParams.get("new") === "1") {
        localStorage.removeItem(chatConversationStorageKey)
        if (cancelled) return
        setConversationId(null)
        setMessages([])
        setInitError(null)
        setSending(false)
        router.replace(CHAT_PATH, { scroll: false })
        setSessionReady(true)
        return
      }

      const openId = searchParams.get(CHAT_CONVERSATION_ID_PARAM)
      if (openId && UUID_RE.test(openId)) {
        try {
          const rows = await fetchChatMessages(token, openId)
          if (cancelled) return
          localStorage.setItem(chatConversationStorageKey, openId)
          setConversationId(openId)
          setMessages(rows.map(rowToMessage))
          setInitError(null)
          router.replace(CHAT_PATH, { scroll: false })
        } catch (loadErr) {
          const detail =
            loadErr instanceof Error ? loadErr.message : "Could not load chat"
          if (cancelled) return
          setInitError(
            detail.toLowerCase().includes("not found")
              ? "Conversation not found"
              : detail,
          )
          router.replace(CHAT_PATH, { scroll: false })
        } finally {
          if (!cancelled) setSessionReady(true)
        }
        return
      }

      const id =
        typeof window !== "undefined"
          ? localStorage.getItem(chatConversationStorageKey)
          : null

      try {
        if (!id) {
          if (cancelled) return
          setConversationId(null)
          setMessages([])
          setInitError(null)
        } else {
          try {
            const rows = await fetchChatMessages(token, id)
            if (cancelled) return
            setConversationId(id)
            setMessages(rows.map(rowToMessage))
            setInitError(null)
          } catch (loadErr) {
            const detail =
              loadErr instanceof Error ? loadErr.message : "Could not load chat"
            if (detail.toLowerCase().includes("not found")) {
              localStorage.removeItem(chatConversationStorageKey)
              if (cancelled) return
              setConversationId(null)
              setMessages([])
              setInitError(null)
            } else {
              throw loadErr
            }
          }
        }
      } catch (e) {
        if (cancelled) return
        setInitError(e instanceof Error ? e.message : "Could not load chat")
      } finally {
        if (!cancelled) setSessionReady(true)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [router, searchParams])

  const handleSubmit = useCallback(
    async (message: unknown) => {
      const token = getToken()
      const rawText =
        typeof message === "string"
          ? message
          : typeof message === "object" &&
              message !== null &&
              "text" in message &&
              typeof (message as { text?: unknown }).text === "string"
            ? (message as { text: string }).text
            : ""
      const trimmed = rawText.trim()

      if (!token) { setInitError("Not signed in. Please log in again."); return }
      if (!trimmed) { setInitError("Enter a message to send."); return }
      if (sending) { setInitError("Still sending — wait for it to finish."); return }

      let activeConversationId = conversationId
      if (!activeConversationId) {
        try {
          const conv = await createChatConversation(token, {})
          activeConversationId = conv.id
          localStorage.setItem(chatConversationStorageKey, conv.id)
          setConversationId(conv.id)
          notifyChatConversationsUpdated()
        } catch (e) {
          setInitError(e instanceof Error ? e.message : "Could not start conversation")
          return
        }
      }

      const tempUserId = makeTempId("pending-user")
      const tempAssistantId = makeTempId("pending-assistant")

      setSending(true)
      setInitError(null)
      setMessages(prev => [
        ...prev,
        { id: tempUserId, from: "user", text: trimmed, content_format: "plain" },
        { id: tempAssistantId, from: "assistant", text: "", content_format: "markdown", pending: true, subagents: [], toolCalls: [], todos: [] },
      ])

      // Local subagent map — updated as SSE events arrive, then flushed into message state.
      const subagentMap = new Map<string, SubagentInfo>()
      const toolCallMap = new Map<string, ToolCallInfo>()

      const flushSubagents = () =>
        setMessages(prev =>
          prev.map(m =>
            m.id === tempAssistantId
              ? { ...m, subagents: Array.from(subagentMap.values()) }
              : m,
          ),
        )

      const flushToolCalls = () =>
        setMessages(prev =>
          prev.map(m =>
            m.id === tempAssistantId
              ? { ...m, toolCalls: Array.from(toolCallMap.values()) }
              : m,
          ),
        )

      // Throttled flush for high-frequency token events (≤ every 80 ms).
      let tokenFlushTimer: ReturnType<typeof setTimeout> | null = null
      const flushSubagentsThrottled = () => {
        if (tokenFlushTimer) return
        tokenFlushTimer = setTimeout(() => {
          tokenFlushTimer = null
          flushSubagents()
        }, 80)
      }

      try {
        for await (const event of streamChatMessage(token, activeConversationId, trimmed)) {
          if (event.type === "token") {
            setMessages(prev =>
              prev.map(m =>
                m.id === tempAssistantId
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
              result: undefined,
              started_at: event.started_at,
              completed_at: undefined,
            })
            // flushSync forces React to render immediately (bypasses batching),
            // so the card appears during the Thinking… phase, not after.
            flushSync(() => flushSubagents())
          } else if (event.type === "subagent_token") {
            const sa = subagentMap.get(event.id)
            if (sa) subagentMap.set(event.id, { ...sa, content: sa.content + event.content })
            flushSubagentsThrottled()
          } else if (event.type === "subagent_done") {
            if (tokenFlushTimer) { clearTimeout(tokenFlushTimer); tokenFlushTimer = null }
            const sa = subagentMap.get(event.id)
            if (sa) subagentMap.set(event.id, {
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
                  m.id === tempAssistantId ? { ...m, todos: event.todos } : m,
                ),
              ),
            )
          } else if (event.type === "saved") {
            setMessages(prev =>
              prev.map(m => {
                if (m.id === tempUserId) return m
                if (m.id === tempAssistantId)
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
                return m
              }),
            )
            notifyChatConversationsUpdated()
          } else if (event.type === "error") {
            setInitError(event.message)
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Stream failed"
        setInitError(msg)
        setMessages(prev =>
          prev.filter(m => m.id !== tempUserId && m.id !== tempAssistantId),
        )
      } finally {
        setSending(false)
      }
    },
    [conversationId, sending],
  )

  const saveConversationTitle = useCallback(async () => {
    if (conversationId == null) return
    const trimmed = titleDraft.trim()
    if (!trimmed) {
      setTitleError("Name cannot be empty")
      return
    }
    if (trimmed === conversationTitle.trim()) {
      setTitleEditing(false)
      setTitleError(null)
      return
    }
    const token = getToken()
    if (!token) {
      setTitleError("Not signed in")
      return
    }
    setTitleSaving(true)
    setTitleError(null)
    try {
      const c = await updateChatConversation(token, conversationId, {
        name: trimmed,
      })
      setConversationTitle(c.name)
      notifyChatConversationsUpdated()
      setTitleEditing(false)
    } catch (e) {
      setTitleError(e instanceof Error ? e.message : "Could not rename")
    } finally {
      setTitleSaving(false)
    }
  }, [conversationId, titleDraft, conversationTitle])

  const cancelTitleEdit = useCallback(() => {
    setTitleEditing(false)
    setTitleDraft("")
    setTitleError(null)
  }, [])

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
      <AppSidebar
        variant="inset"
        activeChatConversationId={conversationId}
      />
      <SidebarInset className="min-h-0 overflow-hidden">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="shrink-0 md:hidden" />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            {titleEditing && conversationId ? (
              <>
                <Input
                  autoFocus
                  value={titleDraft}
                  onChange={e => setTitleDraft(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === "Enter") {
                      e.preventDefault()
                      void saveConversationTitle()
                    } else if (e.key === "Escape") {
                      e.preventDefault()
                      cancelTitleEdit()
                    }
                  }}
                  onBlur={() => {
                    if (!titleSaving) cancelTitleEdit()
                  }}
                  disabled={titleSaving}
                  className="h-9 max-w-md text-base font-medium md:text-base"
                  maxLength={255}
                  aria-invalid={titleError != null}
                />
                {titleError ? (
                  <span className="text-xs text-destructive">{titleError}</span>
                ) : null}
                {titleSaving ? (
                  <span className="text-xs text-muted-foreground">Saving…</span>
                ) : null}
              </>
            ) : (
              <h1
                className={cn(
                  "truncate text-base font-medium",
                  conversationId && sessionReady && "cursor-text",
                )}
                title={
                  conversationId && sessionReady
                    ? "Double-click to rename"
                    : undefined
                }
                onDoubleClick={() => {
                  if (!conversationId || !sessionReady) return
                  setTitleDraft(conversationTitle)
                  setTitleEditing(true)
                  setTitleError(null)
                }}
              >
                {conversationId && !conversationTitle
                  ? "…"
                  : conversationTitle}
              </h1>
            )}
          </div>
        </header>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {!sessionReady ? (
            <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
              <Loader2Icon className="size-5 animate-spin" />
              <span>Loading chat…</span>
            </div>
          ) : (
            <>
              {initError ? (
                <div
                  className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive"
                  role="alert"
                >
                  {initError}
                </div>
              ) : null}
              <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
                <Conversation className="min-h-0 flex-1">
                  <ConversationContent>
                    {messages.length === 0 ? (
                      <ConversationEmptyState
                        title="Start a conversation"
                        description="Messages are saved to the API. Ensure the backend is running and API keys are set for the model."
                        icon={
                          <MessageCircleIcon className="size-12 text-muted-foreground" />
                        }
                      />
                    ) : (
                      <>
                        {messages.map(msg => {
                          const hasSubagents = !!msg.subagents?.length
                          const hasToolCalls = !!msg.toolCalls?.length
                          const hasTodos = !!msg.todos?.length
                          const allDone = hasSubagents && msg.subagents!.every(
                            s => s.status === "complete" || s.status === "error"
                          )
                          const isActiveTurn = !!msg.pending && sending
                          const usePersistedBlocks = !msg.pending && !!msg.blocks?.length
                          // Show thinking only when no other progress indicators are visible
                          const showThinking = isActiveTurn && !msg.text && !hasSubagents && !hasToolCalls && !hasTodos
                          return (
                            <div key={msg.id}>
                              {usePersistedBlocks ? (
                                <AssistantTurnContent
                                  blocks={msg.blocks}
                                  interrupted={msg.interrupted}
                                />
                              ) : (
                                <>
                              {/* Typing indicator: only while pending with no visible progress yet */}
                              {showThinking && (
                                <div className="flex items-center gap-2 px-1 py-2 text-sm text-muted-foreground">
                                  <Loader2Icon className="size-4 shrink-0 animate-spin" />
                                  Thinking…
                                </div>
                              )}

                              {/* Todo list — loading skeleton while agent plans, real items once set_todos fires */}
                              {(hasTodos || (isActiveTurn && hasSubagents)) && (
                                <TodoList
                                  todos={msg.todos ?? []}
                                  isLoading={isActiveTurn && !hasTodos}
                                  className="mb-2 mx-1"
                                />
                              )}

                              {/* Tool call cards — appear as soon as a tool starts */}
                              {hasToolCalls && (
                                <div className="mb-2 space-y-2 px-1">
                                  <ToolCallProgress toolCalls={msg.toolCalls!} />
                                </div>
                              )}

                              {/* Subagent cards — appear as soon as first subagent starts */}
                              {hasSubagents && (
                                <div className="mb-2 space-y-2 px-1">
                                  <SubagentProgress subagents={msg.subagents!} />
                                </div>
                              )}

                              {/* Synthesis indicator: all subagents done, main text still streaming */}
                              {hasSubagents && allDone && sending && msg.pending && (
                                <SynthesisIndicator
                                  subagents={msg.subagents!}
                                  isStreaming={true}
                                  className="mb-2 mx-1"
                                />
                              )}

                              {/* Message bubble — only render when there is text */}
                              {msg.text && (
                                <Message from={msg.from}>
                                  <MessageContent>
                                    {msg.content_format === "markdown" ? (
                                      <MessageResponse>{msg.text}</MessageResponse>
                                    ) : (
                                      msg.text
                                    )}
                                    {msg.interrupted && (
                                      <p className="mt-2 text-sm text-amber-600">
                                        ⏸ Waiting for your approval — reply <strong>yes</strong> or <strong>no</strong>.
                                      </p>
                                    )}
                                  </MessageContent>
                                </Message>
                              )}
                                </>
                              )}
                            </div>
                          )
                        })}
                      </>
                    )}
                  </ConversationContent>
                  <ConversationScrollButton />
                </Conversation>
              </div>
              <div className="shrink-0 border-t bg-background p-4">
                <PromptInputProvider>
                  <PromptInput multiple onSubmit={handleSubmit}>
                    <PromptInputAttachments>
                      {attachment => <PromptInputAttachment data={attachment} />}
                    </PromptInputAttachments>
                    <PromptInputBody>
                      <PromptInputTextarea placeholder="Type your message…" />
                    </PromptInputBody>
                    <PromptInputFooter>
                      <PromptInputTools>
                        <PromptInputActionMenu>
                          <PromptInputActionMenuTrigger />
                          <PromptInputActionMenuContent>
                            <PromptInputActionAddAttachments />
                          </PromptInputActionMenuContent>
                        </PromptInputActionMenu>
                      </PromptInputTools>
                      <PromptInputSubmit
                        disabled={sending || !sessionReady}
                        status={sending ? "submitted" : undefined}
                      />
                    </PromptInputFooter>
                  </PromptInput>
                </PromptInputProvider>
              </div>
            </>
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-svh items-center justify-center gap-2 text-muted-foreground">
          <Loader2Icon className="size-5 animate-spin" />
          <span>Loading chat…</span>
        </div>
      }
    >
      <ChatPageContent />
    </Suspense>
  )
}
