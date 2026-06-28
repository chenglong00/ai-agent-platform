"use client"

import { GlobeIcon, Loader2Icon } from "lucide-react"
import { memo, useEffect, useRef, useState } from "react"

import { browserLiveWsUrl } from "@/lib/chat"
import { cn } from "@/lib/utils"

type BrowserLivePanelProps = {
  accessToken: string
  active?: boolean
  className?: string
}

export const BrowserLivePanel = memo(function BrowserLivePanel({
  accessToken,
  active = true,
  className,
}: BrowserLivePanelProps) {
  const [imageSrc, setImageSrc] = useState<string | null>(null)
  const [pageUrl, setPageUrl] = useState("")
  const [status, setStatus] = useState<"connecting" | "live" | "waiting" | "error">(
    "connecting",
  )
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!active || !accessToken.trim()) {
      return
    }

    let cancelled = false
    const ws = new WebSocket(browserLiveWsUrl(accessToken))
    wsRef.current = ws

    ws.onopen = () => {
      if (!cancelled) setStatus("waiting")
    }

    ws.onmessage = (event) => {
      if (cancelled) return
      try {
        const msg = JSON.parse(String(event.data)) as {
          type?: string
          image_base64?: string
          url?: string
        }
        if (msg.type === "browser_frame" && msg.image_base64) {
          setImageSrc(`data:image/jpeg;base64,${msg.image_base64}`)
          setPageUrl(msg.url ?? "")
          setStatus("live")
        } else if (msg.type === "browser_live_ready" || msg.type === "browser_live_ping") {
          setStatus(prev => (prev === "live" ? prev : "waiting"))
        }
      } catch {
        /* ignore malformed frames */
      }
    }

    ws.onerror = () => {
      if (!cancelled) setStatus("error")
    }

    ws.onclose = () => {
      if (!cancelled) setStatus(prev => (prev === "error" ? prev : "waiting"))
    }

    return () => {
      cancelled = true
      ws.close()
      wsRef.current = null
    }
  }, [accessToken, active])

  if (!active) return null

  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border border-border/60 bg-muted/10",
        className,
      )}
    >
      <div className="flex items-center gap-2 border-b border-border/50 px-2.5 py-1.5 text-xs">
        <GlobeIcon className="size-3 shrink-0 text-muted-foreground" />
        <span className="font-medium">Browser live view</span>
        {status === "connecting" || status === "waiting" ? (
          <Loader2Icon className="ml-auto size-3 animate-spin text-primary" />
        ) : null}
        {status === "live" ? (
          <span className="ml-auto text-emerald-600">Live</span>
        ) : null}
        {status === "error" ? (
          <span className="ml-auto text-destructive">Disconnected</span>
        ) : null}
      </div>

      <div className="relative flex min-h-40 items-center justify-center bg-background/80 p-2">
        {imageSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageSrc}
            alt="Live browser view"
            className="max-h-72 w-full rounded border border-border/40 object-contain"
          />
        ) : (
          <p className="px-4 text-center text-xs text-muted-foreground">
            {status === "error"
              ? "Could not connect to the browser stream."
              : "Waiting for the agent to open the browser…"}
          </p>
        )}
      </div>

      {pageUrl ? (
        <p className="truncate border-t border-border/50 px-2.5 py-1 text-[11px] text-muted-foreground">
          {pageUrl}
        </p>
      ) : null}
    </div>
  )
})
