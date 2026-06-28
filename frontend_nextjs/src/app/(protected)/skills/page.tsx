"use client"

import {
  CheckCircle2Icon,
  EyeIcon,
  Loader2Icon,
  PencilIcon,
  PlusIcon,
  SparklesIcon,
  Trash2Icon,
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
import { Checkbox } from "@/components/ui/checkbox"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { getToken } from "@/lib/auth"
import {
  createSkill,
  defaultSkillAccess,
  defaultSkillDraft,
  deleteSkill,
  fetchBuiltinSkill,
  fetchBuiltinSkills,
  fetchSkill,
  fetchSkillOptions,
  fetchSkills,
  formatAgentSkillView,
  updateSkill,
  visibilityLabel,
  type SkillDetail,
  type SkillOptions,
  type SkillSummary,
  type Visibility,
} from "@/lib/skills"
import { cn } from "@/lib/utils"

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

type EditorTab = "edit" | "preview" | "agent"

function SkillMarkdownPreview({ content }: { content: string }) {
  if (!content.trim()) {
    return (
      <p className="text-sm text-muted-foreground">
        No instructions yet. Switch to Edit to add content.
      </p>
    )
  }
  return (
    <ScrollArea className="max-h-[480px] rounded-md border bg-muted/20 p-4">
      <MessageResponse>{content}</MessageResponse>
    </ScrollArea>
  )
}

export default function SkillsPage() {
  const [options, setOptions] = useState<SkillOptions | null>(null)
  const [builtins, setBuiltins] = useState<SkillSummary[]>([])
  const [skills, setSkills] = useState<SkillSummary[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [activeBuiltinSlug, setActiveBuiltinSlug] = useState<string | null>(null)
  const [isBuiltinView, setIsBuiltinView] = useState(false)
  const [editorTab, setEditorTab] = useState<EditorTab>("edit")
  const [openingBuiltin, setOpeningBuiltin] = useState(false)
  const [draft, setDraft] = useState(defaultSkillDraft())
  const [canManage, setCanManage] = useState(false)
  const [isNew, setIsNew] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const activeSkill = useMemo(
    () => skills.find(s => s.id === activeId) ?? null,
    [skills, activeId],
  )

  const loadLists = useCallback(async () => {
    const token = getToken()
    if (!token) return
    const [builtinList, customList] = await Promise.all([
      fetchBuiltinSkills(token),
      fetchSkills(token),
    ])
    setBuiltins(builtinList)
    setSkills(customList)
    return customList
  }, [])

  const applyDetail = useCallback((detail: SkillDetail, tab?: EditorTab) => {
    setDraft({
      name: detail.name,
      description: detail.description,
      content: detail.content,
      slug: detail.slug,
      enabled: detail.enabled,
      access: detail.access,
    })
    setCanManage(detail.can_manage)
    setIsNew(false)
    if (tab) {
      setEditorTab(tab)
    } else if (!detail.can_manage) {
      setEditorTab("preview")
    }
  }, [])

  const loadInitial = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const [opts, customList] = await Promise.all([
        fetchSkillOptions(token),
        loadLists(),
      ])
      setOptions(opts)
      if (customList && customList.length > 0) {
        const detail = await fetchSkill(token, customList[0].id)
        setActiveId(detail.id)
        applyDetail(detail)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load skills")
    } finally {
      setLoading(false)
    }
  }, [applyDetail, loadLists])

  useEffect(() => {
    void loadInitial()
  }, [loadInitial])

  const openSkill = async (skill: SkillSummary) => {
    const token = getToken()
    if (!token) return
    setError(null)
    setSuccess(null)
    setIsBuiltinView(false)
    setActiveBuiltinSlug(null)
    setEditorTab("edit")
    try {
      const detail = await fetchSkill(token, skill.id)
      setActiveId(skill.id)
      applyDetail(detail)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open skill")
    }
  }

  const openBuiltinSkill = async (skill: SkillSummary) => {
    const token = getToken()
    if (!token) return
    setError(null)
    setSuccess(null)
    setOpeningBuiltin(true)
    setIsBuiltinView(true)
    setActiveBuiltinSlug(skill.slug)
    setActiveId(null)
    setIsNew(false)
    setCanManage(false)
    setEditorTab("preview")
    try {
      const detail = await fetchBuiltinSkill(token, skill.slug)
      applyDetail(detail, "preview")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open built-in skill")
      setIsBuiltinView(false)
      setActiveBuiltinSlug(null)
    } finally {
      setOpeningBuiltin(false)
    }
  }

  const startNewSkill = () => {
    setActiveId(null)
    setActiveBuiltinSlug(null)
    setIsBuiltinView(false)
    setEditorTab("edit")
    setIsNew(true)
    setCanManage(true)
    setDraft(defaultSkillDraft())
    setSuccess(null)
    setError(null)
  }

  const handleSave = async () => {
    const token = getToken()
    if (!token) return
    if (!draft.name.trim() || !draft.content.trim()) {
      setError("Name and instructions are required.")
      return
    }
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      if (isNew) {
        const created = await createSkill(token, draft)
        await loadLists()
        setActiveId(created.id)
        applyDetail(created)
        setSuccess(`Created skill "${created.name}".`)
      } else if (activeId) {
        const updated = await updateSkill(token, activeId, draft)
        await loadLists()
        applyDetail(updated)
        setSuccess(`Saved "${updated.name}".`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save skill")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!activeId || !activeSkill?.is_owner) return
    const label = activeSkill.name
    if (
      !window.confirm(
        `Delete "${label}"? This removes the skill for all users who had access.`,
      )
    ) {
      return
    }
    const token = getToken()
    if (!token) return
    setDeleting(true)
    setError(null)
    setSuccess(null)
    try {
      await deleteSkill(token, activeId)
      const list = await loadLists()
      if (list && list.length > 0) {
        await openSkill(list[0])
      } else {
        startNewSkill()
      }
      setSuccess(`Deleted "${label}".`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete skill")
    } finally {
      setDeleting(false)
    }
  }

  const access = draft.access ?? defaultSkillAccess()
  const agentPreview = formatAgentSkillView(
    draft.name || "Untitled skill",
    draft.description ?? "",
    draft.content,
  )
  const showPanel = isNew || activeId !== null || isBuiltinView
  const canEdit = (canManage || isNew) && !isBuiltinView
  const showEditTab = canEdit

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <SparklesIcon className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">Skills</h1>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 lg:p-6">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}
          {success ? (
            <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-800 dark:text-emerald-300">
              <CheckCircle2Icon className="size-4 shrink-0" />
              {success}
            </div>
          ) : null}

          <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">Your skills</CardTitle>
                    <Button size="sm" variant="outline" onClick={startNewSkill}>
                      <PlusIcon className="size-4" />
                      New
                    </Button>
                  </div>
                  <CardDescription>
                    Custom workflows the agent can load with read_skill
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0 pb-4">
                  {loading ? (
                    <div className="flex items-center gap-2 px-4 py-6 text-sm text-muted-foreground">
                      <Loader2Icon className="size-4 animate-spin" />
                      Loading…
                    </div>
                  ) : skills.length === 0 ? (
                    <p className="px-4 py-4 text-sm text-muted-foreground">
                      No custom skills yet. Click New to create one.
                    </p>
                  ) : (
                    <ScrollArea className="max-h-[320px]">
                      <ul className="space-y-1 px-2">
                        {skills.map(skill => (
                          <li key={skill.id}>
                            <button
                              type="button"
                              onClick={() => void openSkill(skill)}
                              className={cn(
                                "flex w-full flex-col rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50",
                                activeId === skill.id && "border-primary/40 bg-muted/40",
                              )}
                            >
                              <span className="flex items-center justify-between gap-2">
                                <span className="truncate font-medium">{skill.name}</span>
                                {!skill.enabled ? (
                                  <Badge variant="outline" className="shrink-0 text-xs">
                                    Off
                                  </Badge>
                                ) : null}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {visibilityLabel(
                                  skill.access.visibility,
                                  options?.access_visibility_options,
                                )}
                                {skill.is_owner ? " · yours" : ""}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </ScrollArea>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Built-in skills</CardTitle>
                  <CardDescription>Shipped with the platform (read-only)</CardDescription>
                </CardHeader>
                <CardContent>
                  {builtins.length === 0 ? (
                    <p className="text-sm text-muted-foreground">None installed.</p>
                  ) : (
                    <ul className="space-y-2">
                      {builtins.map(skill => (
                        <li key={skill.id}>
                          <button
                            type="button"
                            onClick={() => void openBuiltinSkill(skill)}
                            className={cn(
                              "flex w-full flex-col rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50",
                              activeBuiltinSlug === skill.slug &&
                                "border-primary/40 bg-muted/40",
                            )}
                          >
                            <span className="font-medium">{skill.name}</span>
                            <span className="text-xs text-muted-foreground">
                              {skill.description}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card className="min-h-0">
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle className="text-base">
                    {isNew
                      ? "New skill"
                      : draft.name || (isBuiltinView ? "Built-in skill" : "Skill editor")}
                  </CardTitle>
                  {isBuiltinView ? (
                    <Badge variant="secondary">Built-in</Badge>
                  ) : null}
                  {openingBuiltin ? (
                    <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
                  ) : null}
                </div>
                <CardDescription>
                  {isBuiltinView
                    ? "Read-only preview of platform skills the agent can load"
                    : "Define instructions and who can use this skill in chat"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!showPanel ? (
                  <p className="text-sm text-muted-foreground">
                    Select a skill or create a new one.
                  </p>
                ) : (
                  <>
                    <Tabs
                      value={editorTab}
                      onValueChange={value => setEditorTab(value as EditorTab)}
                    >
                      <TabsList>
                        {showEditTab ? (
                          <TabsTrigger value="edit">
                            <PencilIcon className="size-3.5" />
                            Edit
                          </TabsTrigger>
                        ) : null}
                        <TabsTrigger value="preview">
                          <EyeIcon className="size-3.5" />
                          Preview
                        </TabsTrigger>
                        <TabsTrigger value="agent">Agent view</TabsTrigger>
                      </TabsList>

                      {showEditTab ? (
                        <TabsContent value="edit" className="mt-4 space-y-4">
                          <div className="grid gap-4 sm:grid-cols-2">
                            <div className="space-y-2">
                              <Label htmlFor="skill-name">Name</Label>
                              <Input
                                id="skill-name"
                                value={draft.name}
                                onChange={e =>
                                  setDraft(prev => ({ ...prev, name: e.target.value }))
                                }
                                placeholder="Code review"
                              />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="skill-slug">Slug (optional)</Label>
                              <Input
                                id="skill-slug"
                                value={draft.slug ?? ""}
                                onChange={e =>
                                  setDraft(prev => ({ ...prev, slug: e.target.value }))
                                }
                                placeholder="code-review"
                              />
                            </div>
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="skill-description">Description</Label>
                            <Input
                              id="skill-description"
                              value={draft.description ?? ""}
                              onChange={e =>
                                setDraft(prev => ({
                                  ...prev,
                                  description: e.target.value,
                                }))
                              }
                              placeholder="When the agent should use this skill"
                            />
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="skill-content">Instructions</Label>
                            <Textarea
                              id="skill-content"
                              value={draft.content}
                              onChange={e =>
                                setDraft(prev => ({ ...prev, content: e.target.value }))
                              }
                              placeholder="Markdown instructions for the agent…"
                              className="min-h-[220px] font-mono text-sm"
                            />
                          </div>

                          <div className="flex items-center justify-between rounded-md border px-3 py-2">
                            <div>
                              <p className="text-sm font-medium">Enabled</p>
                              <p className="text-xs text-muted-foreground">
                                Disabled skills are hidden from the agent
                              </p>
                            </div>
                            <Switch
                              checked={draft.enabled ?? true}
                              onCheckedChange={checked =>
                                setDraft(prev => ({ ...prev, enabled: checked }))
                              }
                            />
                          </div>

                          <div className="space-y-3 rounded-md border p-4">
                            <div className="space-y-2">
                              <Label>Access</Label>
                              <Select
                                value={access.visibility}
                                onValueChange={value =>
                                  setDraft(prev => ({
                                    ...prev,
                                    access: {
                                      ...defaultSkillAccess(),
                                      ...prev.access,
                                      visibility: value as Visibility,
                                    },
                                  }))
                                }
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {options?.access_visibility_options.map(opt => (
                                    <SelectItem key={opt.id} value={opt.id}>
                                      {opt.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <p className="text-xs text-muted-foreground">
                                {
                                  options?.access_visibility_options.find(
                                    o => o.id === access.visibility,
                                  )?.description
                                }
                              </p>
                            </div>

                            {access.visibility === "group" ? (
                              <div className="space-y-2">
                                <Label>Allowed groups</Label>
                                {(options?.groups.length ?? 0) === 0 ? (
                                  <p className="text-xs text-muted-foreground">
                                    You are not a member of any groups yet.
                                  </p>
                                ) : (
                                  <div className="space-y-2">
                                    {options?.groups.map(group => {
                                      const checked = access.allowed_group_ids.includes(
                                        group.id,
                                      )
                                      return (
                                        <label
                                          key={group.id}
                                          className="flex cursor-pointer items-center gap-2 text-sm"
                                        >
                                          <Checkbox
                                            checked={checked}
                                            onCheckedChange={value => {
                                              setDraft(prev => {
                                                const current =
                                                  prev.access ?? defaultSkillAccess()
                                                return {
                                                  ...prev,
                                                  access: {
                                                    ...current,
                                                    allowed_group_ids: value
                                                      ? [
                                                          ...current.allowed_group_ids,
                                                          group.id,
                                                        ]
                                                      : current.allowed_group_ids.filter(
                                                          id => id !== group.id,
                                                        ),
                                                  },
                                                }
                                              })
                                            }}
                                          />
                                          {group.name}
                                        </label>
                                      )
                                    })}
                                  </div>
                                )}
                              </div>
                            ) : null}

                            {access.visibility === "role" ? (
                              <div className="space-y-2">
                                <Label>Allowed roles</Label>
                                <div className="space-y-2">
                                  {options?.role_options.map(role => {
                                    const checked = access.allowed_roles.includes(role.id)
                                    return (
                                      <label
                                        key={role.id}
                                        className="flex cursor-pointer items-center gap-2 text-sm"
                                      >
                                        <Checkbox
                                          checked={checked}
                                          onCheckedChange={value => {
                                            setDraft(prev => {
                                              const current =
                                                prev.access ?? defaultSkillAccess()
                                              return {
                                                ...prev,
                                                access: {
                                                  ...current,
                                                  allowed_roles: value
                                                    ? [...current.allowed_roles, role.id]
                                                    : current.allowed_roles.filter(
                                                        id => id !== role.id,
                                                      ),
                                                },
                                              }
                                            })
                                          }}
                                        />
                                        {role.label}
                                      </label>
                                    )
                                  })}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        </TabsContent>
                      ) : null}

                      <TabsContent value="preview" className="mt-4 space-y-4">
                        {!showEditTab ? (
                          <div className="space-y-1">
                            <p className="text-lg font-medium">{draft.name}</p>
                            {draft.description ? (
                              <p className="text-sm text-muted-foreground">
                                {draft.description}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                        <div className="space-y-2">
                          <Label>Instructions</Label>
                          <SkillMarkdownPreview content={draft.content} />
                        </div>
                      </TabsContent>

                      <TabsContent value="agent" className="mt-4 space-y-4">
                        <p className="text-xs text-muted-foreground">
                          This is what the agent receives when it calls read_skill.
                        </p>
                        <SkillMarkdownPreview content={agentPreview} />
                      </TabsContent>
                    </Tabs>

                    {!canEdit && !isNew && !isBuiltinView ? (
                      <p className="text-xs text-muted-foreground">
                        Only the skill owner can edit this skill. Use Preview or Agent
                        view to inspect instructions.
                      </p>
                    ) : null}

                    {!isNew && !isBuiltinView && activeSkill?.updated_at ? (
                      <p className="text-xs text-muted-foreground">
                        Last updated {formatDate(activeSkill.updated_at)}
                      </p>
                    ) : null}

                    {canEdit ? (
                      <div className="flex flex-wrap gap-2 pt-2">
                        <Button disabled={saving} onClick={() => void handleSave()}>
                          {saving ? (
                            <>
                              <Loader2Icon className="size-4 animate-spin" />
                              Saving…
                            </>
                          ) : isNew ? (
                            "Create skill"
                          ) : (
                            "Save changes"
                          )}
                        </Button>
                        {!isNew && activeSkill?.is_owner ? (
                          <Button
                            variant="outline"
                            className="border-destructive/40 text-destructive hover:bg-destructive/5"
                            disabled={deleting}
                            onClick={() => void handleDelete()}
                          >
                            {deleting ? (
                              <Loader2Icon className="size-4 animate-spin" />
                            ) : (
                              <Trash2Icon className="size-4" />
                            )}
                            Delete
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
