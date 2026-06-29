"use client"

import {
  BotIcon,
  ExternalLinkIcon,
  Loader2Icon,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react"
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import {
  deleteSubagent,
  fetchSubagents,
  formatDateTime,
  refreshSubagent,
  registerSubagent,
  updateSubagent,
  type SubagentSummary,
} from "@/lib/subagent"

function statusBadge(item: SubagentSummary) {
  if (item.last_error) {
    return <Badge variant="destructive">Error</Badge>
  }
  if (!item.enabled) {
    return <Badge variant="secondary">Disabled</Badge>
  }
  return <Badge>Enabled</Badge>
}

export default function SubAgentPage() {
  const [items, setItems] = useState<SubagentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [registering, setRegistering] = useState(false)
  const [agentUrl, setAgentUrl] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [description, setDescription] = useState("")

  const loadSubagents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await fetchSubagents())
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load subagents")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadSubagents()
  }, [loadSubagents])

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    if (!agentUrl.trim()) return
    setRegistering(true)
    setError(null)
    try {
      await registerSubagent(undefined, {
        agent_url: agentUrl.trim(),
        name: displayName.trim() || undefined,
        description: description.trim() || undefined,
      })
      setDialogOpen(false)
      setAgentUrl("")
      setDisplayName("")
      setDescription("")
      await loadSubagents()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not register agent")
    } finally {
      setRegistering(false)
    }
  }

  async function handleToggle(id: string, enabled: boolean) {
    setBusyId(id)
    setError(null)
    try {
      await updateSubagent(undefined, id, { enabled })
      await loadSubagents()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update subagent")
    } finally {
      setBusyId(null)
    }
  }

  async function handleRefresh(id: string) {
    setBusyId(id)
    setError(null)
    try {
      await refreshSubagent(undefined, id)
      await loadSubagents()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh agent card")
      await loadSubagents()
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Remove this subagent registration?")) return
    setBusyId(id)
    setError(null)
    try {
      await deleteSubagent(undefined, id)
      await loadSubagents()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete subagent")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <BotIcon className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">SubAgent</h1>
          <div className="ml-auto">
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <PlusIcon className="mr-2 size-4" />
                  Register agent
                </Button>
              </DialogTrigger>
              <DialogContent>
                <form onSubmit={e => void handleRegister(e)}>
                  <DialogHeader>
                    <DialogTitle>Register A2A agent</DialogTitle>
                    <DialogDescription>
                      Enter the base URL of a remote agent. We fetch its Agent Card
                      from <code>/.well-known/agent-card.json</code> using the
                      Agent-to-Agent (A2A) protocol.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                      <Label htmlFor="agent-url">Agent URL</Label>
                      <Input
                        id="agent-url"
                        placeholder="https://my-agent.example.com"
                        value={agentUrl}
                        onChange={e => setAgentUrl(e.target.value)}
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="display-name">Display name (optional)</Label>
                      <Input
                        id="display-name"
                        placeholder="Override name from agent card"
                        value={displayName}
                        onChange={e => setDisplayName(e.target.value)}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="description">Description (optional)</Label>
                      <Textarea
                        id="description"
                        placeholder="Override description from agent card"
                        value={description}
                        rows={3}
                        onChange={e => setDescription(e.target.value)}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button type="submit" disabled={registering || !agentUrl.trim()}>
                      {registering ? (
                        <Loader2Icon className="mr-2 size-4 animate-spin" />
                      ) : null}
                      Register
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 lg:p-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">A2A subagent registry</CardTitle>
              <CardDescription>
                Register remote agents that expose an A2A Agent Card. The deep agent
                can delegate specialized tasks to enabled subagents.
              </CardDescription>
            </CardHeader>
          </Card>

          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              Loading subagents…
            </div>
          ) : items.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                No subagents registered yet. Click{" "}
                <span className="font-medium text-foreground">Register agent</span>{" "}
                and provide an A2A agent base URL.
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {items.map(item => {
                const isBusy = busyId === item.id
                return (
                  <Card key={item.id} className="flex flex-col">
                    <CardHeader className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <div className="rounded-md border p-2 text-muted-foreground">
                            <BotIcon className="size-5" />
                          </div>
                          <div>
                            <CardTitle className="text-base">{item.name}</CardTitle>
                            {item.agent_version ? (
                              <p className="text-xs text-muted-foreground">
                                v{item.agent_version}
                              </p>
                            ) : null}
                          </div>
                        </div>
                        {statusBadge(item)}
                      </div>
                      {item.description ? (
                        <CardDescription>{item.description}</CardDescription>
                      ) : null}
                    </CardHeader>

                    <CardContent className="mt-auto space-y-4">
                      <div className="space-y-1 text-xs text-muted-foreground">
                        <p className="font-mono break-all">{item.agent_url}</p>
                        <p>
                          Streaming: {item.streaming ? "yes" : "no"} · Skills:{" "}
                          {item.skills.length}
                        </p>
                        {item.last_verified_at ? (
                          <p>Verified: {formatDateTime(item.last_verified_at)}</p>
                        ) : null}
                        {item.last_error ? (
                          <p className="text-destructive">{item.last_error}</p>
                        ) : null}
                      </div>

                      <div className="flex items-center justify-between rounded-md border px-3 py-2">
                        <span className="text-sm">Enabled for deep agent</span>
                        <Switch
                          checked={item.enabled}
                          disabled={isBusy}
                          onCheckedChange={checked =>
                            void handleToggle(item.id, checked)
                          }
                        />
                      </div>

                      {item.skills.length > 0 ? (
                        <ScrollArea className="h-28 rounded-md border p-2">
                          <ul className="space-y-2 text-xs">
                            {item.skills.map(skill => (
                              <li key={skill.id || skill.name}>
                                <span className="font-medium">{skill.name}</span>
                                {skill.description ? (
                                  <span className="text-muted-foreground">
                                    {" "}
                                    — {skill.description}
                                  </span>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </ScrollArea>
                      ) : null}

                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => void handleRefresh(item.id)}
                        >
                          {isBusy ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                          ) : (
                            <RefreshCwIcon className="mr-2 size-4" />
                          )}
                          Refresh card
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={isBusy}
                          onClick={() => void handleDelete(item.id)}
                        >
                          <Trash2Icon className="mr-2 size-4" />
                          Remove
                        </Button>
                        <Button size="sm" variant="ghost" asChild>
                          <a href={item.agent_url} target="_blank" rel="noreferrer">
                            <ExternalLinkIcon className="mr-2 size-4" />
                            Open
                          </a>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
