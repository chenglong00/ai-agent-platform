"use client"

import {
  CalendarIcon,
  ExternalLinkIcon,
  HardDriveIcon,
  Loader2Icon,
  MailIcon,
  PlugIcon,
  RefreshCwIcon,
  UnplugIcon,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"

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
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Switch } from "@/components/ui/switch"
import { getToken } from "@/lib/auth"
import {
  beginConnectorOAuth,
  connectorIconId,
  disconnectConnector,
  fetchConnectorTools,
  fetchConnectors,
  formatDateTime,
  updateConnectorEnabled,
  type ConnectorStatusItem,
  type ConnectorToolInfo,
} from "@/lib/connector"

function ConnectorIcon({ id }: { id: string }) {
  const kind = connectorIconId(id)
  if (kind === "calendar") return <CalendarIcon className="size-5" />
  if (kind === "drive") return <HardDriveIcon className="size-5" />
  if (kind === "mail") return <MailIcon className="size-5" />
  return <PlugIcon className="size-5" />
}

function statusBadge(item: ConnectorStatusItem) {
  if (!item.connection?.connected) {
    return <Badge variant="outline">Not connected</Badge>
  }
  if (!item.connection.enabled) {
    return <Badge variant="secondary">Connected · disabled</Badge>
  }
  return <Badge>Connected</Badge>
}

export default function ConnectorPage() {
  const searchParams = useSearchParams()
  const [items, setItems] = useState<ConnectorStatusItem[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [toolsById, setToolsById] = useState<Record<string, ConnectorToolInfo[]>>({})
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const oauthNotice = useMemo(() => {
    const status = searchParams.get("status")
    const connector = searchParams.get("connector")
    if (status === "connected" && connector) {
      return `Connected ${connector.replace(/_/g, " ")} successfully.`
    }
    if (status === "error") {
      return searchParams.get("message") ?? "OAuth authorization failed."
    }
    return null
  }, [searchParams])

  const loadConnectors = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      setItems(await fetchConnectors(token))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load connectors")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadConnectors()
  }, [loadConnectors])

  useEffect(() => {
    if (oauthNotice) setNotice(oauthNotice)
  }, [oauthNotice])

  async function handleConnect(connectorId: string) {
    const token = getToken()
    if (!token) return
    setBusyId(connectorId)
    setError(null)
    try {
      const url = await beginConnectorOAuth(token, connectorId)
      window.location.href = url
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start OAuth")
      setBusyId(null)
    }
  }

  async function handleDisconnect(connectorId: string) {
    const token = getToken()
    if (!token) return
    setBusyId(connectorId)
    setError(null)
    try {
      await disconnectConnector(token, connectorId)
      setToolsById(prev => {
        const next = { ...prev }
        delete next[connectorId]
        return next
      })
      await loadConnectors()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not disconnect")
    } finally {
      setBusyId(null)
    }
  }

  async function handleToggle(connectorId: string, enabled: boolean) {
    const token = getToken()
    if (!token) return
    setBusyId(connectorId)
    setError(null)
    try {
      await updateConnectorEnabled(token, connectorId, enabled)
      await loadConnectors()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update connector")
    } finally {
      setBusyId(null)
    }
  }

  async function handleListTools(connectorId: string) {
    const token = getToken()
    if (!token) return
    setBusyId(connectorId)
    setError(null)
    try {
      const tools = await fetchConnectorTools(token, connectorId)
      setToolsById(prev => ({ ...prev, [connectorId]: tools }))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not list MCP tools")
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
          <PlugIcon className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">Connector</h1>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 lg:p-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Enterprise applications</CardTitle>
              <CardDescription>
                Connect Google Workspace services via official remote MCP servers.
                Tokens are encrypted and stored per user.
              </CardDescription>
            </CardHeader>
          </Card>

          {notice ? (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-900 dark:text-emerald-100">
              {notice}
            </div>
          ) : null}

          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              Loading connectors…
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {items.map(item => {
                const connected = Boolean(item.connection?.connected)
                const enabled = item.connection?.enabled ?? false
                const tools = toolsById[item.catalog.id] ?? []
                const isBusy = busyId === item.catalog.id

                return (
                  <Card key={item.catalog.id} className="flex flex-col">
                    <CardHeader className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <div className="rounded-md border p-2 text-muted-foreground">
                            <ConnectorIcon id={item.catalog.id} />
                          </div>
                          <div>
                            <CardTitle className="text-base">{item.catalog.name}</CardTitle>
                            <p className="text-xs text-muted-foreground">{item.catalog.category}</p>
                          </div>
                        </div>
                        {statusBadge(item)}
                      </div>
                      <CardDescription>{item.catalog.description}</CardDescription>
                    </CardHeader>

                    <CardContent className="mt-auto space-y-4">
                      <div className="space-y-1 text-xs text-muted-foreground">
                        <p className="font-mono break-all">{item.catalog.mcp_url}</p>
                        {connected && item.connection?.account_email ? (
                          <p>Account: {item.connection.account_email}</p>
                        ) : null}
                        {connected && item.connection?.last_connected_at ? (
                          <p>Last connected: {formatDateTime(item.connection.last_connected_at)}</p>
                        ) : null}
                        {item.connection?.last_error ? (
                          <p className="text-destructive">{item.connection.last_error}</p>
                        ) : null}
                      </div>

                      {connected ? (
                        <div className="flex items-center justify-between rounded-md border px-3 py-2">
                          <span className="text-sm">Enabled for agent</span>
                          <Switch
                            checked={enabled}
                            disabled={isBusy}
                            onCheckedChange={checked =>
                              void handleToggle(item.catalog.id, checked)
                            }
                          />
                        </div>
                      ) : null}

                      <div className="flex flex-wrap gap-2">
                        {!connected ? (
                          <Button
                            size="sm"
                            disabled={isBusy}
                            onClick={() => void handleConnect(item.catalog.id)}
                          >
                            {isBusy ? (
                              <Loader2Icon className="mr-2 size-4 animate-spin" />
                            ) : null}
                            Connect
                          </Button>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={isBusy}
                              onClick={() => void handleListTools(item.catalog.id)}
                            >
                              {isBusy ? (
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                              ) : (
                                <RefreshCwIcon className="mr-2 size-4" />
                              )}
                              MCP tools
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={isBusy}
                              onClick={() => void handleConnect(item.catalog.id)}
                            >
                              Reconnect
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={isBusy}
                              onClick={() => void handleDisconnect(item.catalog.id)}
                            >
                              <UnplugIcon className="mr-2 size-4" />
                              Disconnect
                            </Button>
                          </>
                        )}
                        <Button size="sm" variant="ghost" asChild>
                          <a
                            href={item.catalog.docs_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLinkIcon className="mr-2 size-4" />
                            Docs
                          </a>
                        </Button>
                      </div>

                      {tools.length > 0 ? (
                        <ScrollArea className="h-28 rounded-md border p-2">
                          <ul className="space-y-2 text-xs">
                            {tools.map(tool => (
                              <li key={tool.name ?? "unknown"}>
                                <span className="font-medium">{tool.name}</span>
                                {tool.description ? (
                                  <span className="text-muted-foreground">
                                    {" "}
                                    — {tool.description}
                                  </span>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </ScrollArea>
                      ) : null}
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
