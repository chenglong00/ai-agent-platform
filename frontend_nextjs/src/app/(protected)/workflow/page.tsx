"use client"

import {
  Loader2Icon,
  PlayIcon,
  PlusIcon,
  Trash2Icon,
  Workflow as WorkflowIcon,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { MessageResponse } from "@/components/ai/message"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
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
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { getToken } from "@/lib/auth"
import {
  createWorkflow,
  defaultWorkflowDraft,
  deleteWorkflow,
  draftToRequestBody,
  fetchWorkflowRuns,
  fetchWorkflows,
  formatDateTime,
  runStatusLabel,
  scheduleTypeLabel,
  triggerWorkflowRun,
  updateWorkflow,
  workflowToDraft,
  type WorkflowDraft,
  type WorkflowRunSummary,
  type WorkflowScheduleType,
  type WorkflowSummary,
} from "@/lib/workflow"

function statusVariant(
  status: WorkflowRunSummary["status"],
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "succeeded") return "default"
  if (status === "failed") return "destructive"
  if (status === "running") return "secondary"
  return "outline"
}

export default function WorkflowPage() {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [runs, setRuns] = useState<WorkflowRunSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [draft, setDraft] = useState<WorkflowDraft>(defaultWorkflowDraft())
  const [loading, setLoading] = useState(true)
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const activeWorkflow = useMemo(
    () => workflows.find(w => w.id === activeId) ?? null,
    [workflows, activeId],
  )

  const loadWorkflows = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const list = await fetchWorkflows(token)
      setWorkflows(list)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load workflows")
    } finally {
      setLoading(false)
    }
  }, [])

  const loadRuns = useCallback(async (workflowId: string) => {
    const token = getToken()
    if (!token) return
    setLoadingRuns(true)
    try {
      setRuns(await fetchWorkflowRuns(token, workflowId))
    } catch {
      setRuns([])
    } finally {
      setLoadingRuns(false)
    }
  }, [])

  useEffect(() => {
    void loadWorkflows()
  }, [loadWorkflows])

  useEffect(() => {
    if (activeId && !isNew) {
      void loadRuns(activeId)
    } else {
      setRuns([])
    }
  }, [activeId, isNew, loadRuns])

  const startNew = () => {
    setIsNew(true)
    setActiveId(null)
    setDraft(defaultWorkflowDraft())
    setSuccess(null)
    setError(null)
  }

  const selectWorkflow = (workflow: WorkflowSummary) => {
    setIsNew(false)
    setActiveId(workflow.id)
    setDraft(workflowToDraft(workflow))
    setSuccess(null)
    setError(null)
  }

  const handleSave = async () => {
    const token = getToken()
    if (!token) return
    if (!draft.name.trim() || !draft.prompt.trim()) {
      setError("Name and prompt are required.")
      return
    }
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const body = draftToRequestBody(draft)
      if (isNew) {
        const created = await createWorkflow(token, body)
        setWorkflows(prev => [created, ...prev])
        setIsNew(false)
        setActiveId(created.id)
        setDraft(workflowToDraft(created))
        setSuccess("Workflow created.")
        await loadRuns(created.id)
      } else if (activeId) {
        const updated = await updateWorkflow(token, activeId, body)
        setWorkflows(prev => prev.map(w => (w.id === updated.id ? updated : w)))
        setDraft(workflowToDraft(updated))
        setSuccess("Workflow saved.")
        await loadRuns(activeId)
      }
      await loadWorkflows()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save workflow")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    const token = getToken()
    if (!token || !activeId) return
    if (!window.confirm("Delete this workflow?")) return
    setDeleting(true)
    setError(null)
    try {
      await deleteWorkflow(token, activeId)
      setWorkflows(prev => prev.filter(w => w.id !== activeId))
      setActiveId(null)
      setIsNew(false)
      setDraft(defaultWorkflowDraft())
      setRuns([])
      setSuccess("Workflow deleted.")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete workflow")
    } finally {
      setDeleting(false)
    }
  }

  const handleRunNow = async () => {
    const token = getToken()
    if (!token || !activeId) return
    setRunning(true)
    setError(null)
    setSuccess(null)
    try {
      const run = await triggerWorkflowRun(token, activeId)
      setRuns(prev => [run, ...prev])
      await loadWorkflows()
      setSuccess(run.status === "succeeded" ? "Run completed." : "Run finished with issues.")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not run workflow")
    } finally {
      setRunning(false)
    }
  }

  const editorVisible = isNew || activeId !== null

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <WorkflowIcon className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">Workflow</h1>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 lg:flex-row lg:p-6">
          <Card className="lg:w-80 lg:shrink-0">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
              <div>
                <CardTitle className="text-base">Workflows</CardTitle>
                <CardDescription>Scheduled deep agent tasks</CardDescription>
              </div>
              <Button size="sm" variant="outline" onClick={startNew}>
                <PlusIcon className="mr-1 size-4" />
                New
              </Button>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2Icon className="size-4 animate-spin" />
                  Loading…
                </div>
              ) : workflows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No workflows yet. Create one to schedule an LLM prompt.
                </p>
              ) : (
                <ScrollArea className="h-[min(420px,50vh)] pr-3">
                  <div className="space-y-1">
                    {workflows.map(workflow => (
                      <button
                        key={workflow.id}
                        type="button"
                        onClick={() => selectWorkflow(workflow)}
                        className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                          activeId === workflow.id && !isNew
                            ? "border-primary bg-muted/50"
                            : "border-transparent hover:bg-muted/40"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-medium">{workflow.name}</span>
                          <Badge variant={workflow.enabled ? "default" : "secondary"}>
                            {workflow.enabled ? "On" : "Off"}
                          </Badge>
                        </div>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          {scheduleTypeLabel[workflow.schedule_type]}
                          {workflow.next_run_at
                            ? ` · next ${formatDateTime(workflow.next_run_at)}`
                            : ""}
                        </p>
                      </button>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>

          <div className="flex min-w-0 flex-1 flex-col gap-4">
            {error ? (
              <div
                className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-2 text-sm text-destructive"
                role="alert"
              >
                {error}
              </div>
            ) : null}
            {success ? (
              <div className="rounded-md border border-emerald-500/30 bg-emerald-500/5 px-4 py-2 text-sm text-emerald-700 dark:text-emerald-300">
                {success}
              </div>
            ) : null}

            {!editorVisible ? (
              <Card className="flex flex-1 items-center justify-center">
                <CardContent className="py-12 text-center text-sm text-muted-foreground">
                  Select a workflow or create a new one.
                </CardContent>
              </Card>
            ) : (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      {isNew ? "New workflow" : activeWorkflow?.name ?? "Workflow"}
                    </CardTitle>
                    <CardDescription>
                      One LLM task (deep agent) with a prompt and a schedule.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="workflow-name">Name</Label>
                        <Input
                          id="workflow-name"
                          value={draft.name}
                          onChange={e => setDraft(d => ({ ...d, name: e.target.value }))}
                          placeholder="Daily summary"
                        />
                      </div>
                      <div className="flex items-end justify-between gap-4 rounded-md border px-3 py-2">
                        <div>
                          <Label htmlFor="workflow-enabled">Enabled</Label>
                          <p className="text-xs text-muted-foreground">
                            Run on schedule automatically
                          </p>
                        </div>
                        <Switch
                          id="workflow-enabled"
                          checked={draft.enabled}
                          onCheckedChange={checked =>
                            setDraft(d => ({ ...d, enabled: checked }))
                          }
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="workflow-description">Description (optional)</Label>
                      <Input
                        id="workflow-description"
                        value={draft.description}
                        onChange={e =>
                          setDraft(d => ({ ...d, description: e.target.value }))
                        }
                        placeholder="What this workflow does"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>Task type</Label>
                      <Input value="LLM (Deep Agent)" disabled />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="workflow-prompt">Prompt</Label>
                      <Textarea
                        id="workflow-prompt"
                        value={draft.prompt}
                        onChange={e => setDraft(d => ({ ...d, prompt: e.target.value }))}
                        placeholder="Summarize my workspace files and suggest next steps."
                        rows={6}
                        className="font-mono text-sm"
                      />
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Schedule</Label>
                        <Select
                          value={draft.schedule_type}
                          onValueChange={value =>
                            setDraft(d => ({
                              ...d,
                              schedule_type: value as WorkflowScheduleType,
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="once">Once</SelectItem>
                            <SelectItem value="daily">Daily</SelectItem>
                            <SelectItem value="interval">Every N minutes</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {draft.schedule_type === "once" ? (
                        <div className="space-y-2">
                          <Label htmlFor="workflow-run-at">Run at (local time)</Label>
                          <Input
                            id="workflow-run-at"
                            type="datetime-local"
                            value={draft.run_at}
                            onChange={e =>
                              setDraft(d => ({ ...d, run_at: e.target.value }))
                            }
                          />
                        </div>
                      ) : null}

                      {draft.schedule_type === "daily" ? (
                        <div className="space-y-2">
                          <Label htmlFor="workflow-run-time">Time (UTC)</Label>
                          <Input
                            id="workflow-run-time"
                            type="time"
                            value={draft.run_time}
                            onChange={e =>
                              setDraft(d => ({ ...d, run_time: e.target.value }))
                            }
                          />
                        </div>
                      ) : null}

                      {draft.schedule_type === "interval" ? (
                        <div className="space-y-2">
                          <Label htmlFor="workflow-interval">Interval (minutes)</Label>
                          <Input
                            id="workflow-interval"
                            type="number"
                            min={5}
                            max={10080}
                            value={draft.interval_minutes}
                            onChange={e =>
                              setDraft(d => ({
                                ...d,
                                interval_minutes: Number(e.target.value) || 5,
                              }))
                            }
                          />
                        </div>
                      ) : null}
                    </div>

                    {!isNew && activeWorkflow ? (
                      <div className="rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                        Next run: {formatDateTime(activeWorkflow.next_run_at)} · Last run:{" "}
                        {formatDateTime(activeWorkflow.last_run_at)}
                      </div>
                    ) : null}

                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => void handleSave()} disabled={saving}>
                        {saving ? (
                          <Loader2Icon className="mr-2 size-4 animate-spin" />
                        ) : null}
                        {isNew ? "Create workflow" : "Save changes"}
                      </Button>
                      {!isNew && activeId ? (
                        <>
                          <Button
                            variant="secondary"
                            onClick={() => void handleRunNow()}
                            disabled={running}
                          >
                            {running ? (
                              <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                              <PlayIcon className="mr-2 size-4" />
                            )}
                            Run now
                          </Button>
                          <Button
                            variant="destructive"
                            onClick={() => void handleDelete()}
                            disabled={deleting}
                          >
                            {deleting ? (
                              <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : (
                              <Trash2Icon className="mr-2 size-4" />
                            )}
                            Delete
                          </Button>
                        </>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>

                {!isNew && activeId ? (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Run history</CardTitle>
                      <CardDescription>Recent scheduled and manual runs</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {loadingRuns ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Loader2Icon className="size-4 animate-spin" />
                          Loading runs…
                        </div>
                      ) : runs.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No runs yet.</p>
                      ) : (
                        <div className="space-y-3">
                          {runs.map(run => (
                            <div key={run.id} className="rounded-md border p-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge variant={statusVariant(run.status)}>
                                  {runStatusLabel[run.status]}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  {formatDateTime(run.finished_at ?? run.started_at ?? run.created_at)}
                                </span>
                              </div>
                              {run.error ? (
                                <p className="mt-2 text-sm text-destructive">{run.error}</p>
                              ) : null}
                              {run.output_text ? (
                                <div className="prose prose-sm dark:prose-invert mt-2 max-w-none">
                                  <MessageResponse>{run.output_text}</MessageResponse>
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ) : null}
              </>
            )}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
