"use client"

import { BrainIcon, Loader2Icon, PlusIcon, Trash2Icon } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

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

import { Label } from "@/components/ui/label"
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
import { Textarea } from "@/components/ui/textarea"
import { getToken } from "@/lib/auth"
import {
  createMemory,
  deleteMemory,
  fetchMemories,
  memoryCategoryLabel,
  type MemoryCategory,
  type UserMemory,
} from "@/lib/memory"

const CATEGORIES: MemoryCategory[] = [
  "fact",
  "preference",
  "profile",
  "goal",
  "other",
]

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export default function MemoryPage() {
  const [memories, setMemories] = useState<UserMemory[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [category, setCategory] = useState<MemoryCategory>("fact")
  const [content, setContent] = useState("")

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      setMemories(await fetchMemories(token))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load memories")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    const token = getToken()
    if (!token || !content.trim()) return
    setSaving(true)
    setError(null)
    try {
      await createMemory(token, { category, content: content.trim() })
      setContent("")
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save memory")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    const token = getToken()
    if (!token) return
    if (!window.confirm("Delete this memory?")) return
    setDeletingId(id)
    setError(null)
    try {
      await deleteMemory(token, id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete memory")
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <BrainIcon className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">Memory</h1>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 lg:p-6">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Add memory</CardTitle>
              <CardDescription>
                Facts and preferences the agent uses across conversations. The
                agent can also save memories automatically during chat.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-[180px_1fr]">
                  <div className="space-y-2">
                    <Label>Category</Label>
                    <Select
                      value={category}
                      onValueChange={v => setCategory(v as MemoryCategory)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CATEGORIES.map(c => (
                          <SelectItem key={c} value={c}>
                            {memoryCategoryLabel[c]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="memory-content">Content</Label>
                    <Textarea
                      id="memory-content"
                      value={content}
                      onChange={e => setContent(e.target.value)}
                      placeholder="Prefers concise answers; works on the platform team…"
                      rows={3}
                    />
                  </div>
                </div>
                <Button type="submit" disabled={saving || !content.trim()}>
                  {saving ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <PlusIcon className="size-4" />
                  )}
                  Save memory
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Stored memories</CardTitle>
              <CardDescription>
                Injected into the agent prompt on each message (up to{" "}
                {process.env.NEXT_PUBLIC_USER_MEMORY_PROMPT_MAX_ITEMS ?? "20"}{" "}
                recent items).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2Icon className="size-4 animate-spin" />
                  Loading…
                </div>
              ) : memories.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No memories yet. Add one above or tell the agent something to
                  remember in chat.
                </p>
              ) : (
                <ul className="space-y-3">
                  {memories.map(m => (
                    <li
                      key={m.id}
                      className="flex items-start justify-between gap-3 rounded-md border px-3 py-3"
                    >
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="secondary">
                            {memoryCategoryLabel[m.category]}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {m.source} · {formatDate(m.updated_at)}
                          </span>
                        </div>
                        <p className="text-sm">{m.content}</p>
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="shrink-0 text-destructive hover:text-destructive"
                        disabled={deletingId === m.id}
                        onClick={() => void handleDelete(m.id)}
                        aria-label="Delete memory"
                      >
                        {deletingId === m.id ? (
                          <Loader2Icon className="size-4 animate-spin" />
                        ) : (
                          <Trash2Icon className="size-4" />
                        )}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
