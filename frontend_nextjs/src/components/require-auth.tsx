"use client"

import { useLayoutEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { fetchCurrentUser } from "@/lib/api"

/**
 * Gates children until the session cookie validates via /auth/me.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [allowed, setAllowed] = useState(false)

  useLayoutEffect(() => {
    let cancelled = false
    void fetchCurrentUser().then(result => {
      if (cancelled) return
      if (!result.user) {
        router.replace("/login")
        return
      }
      setAllowed(true)
    })
    return () => {
      cancelled = true
    }
  }, [router])

  if (!allowed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Redirecting…</p>
      </div>
    )
  }

  return <>{children}</>
}
