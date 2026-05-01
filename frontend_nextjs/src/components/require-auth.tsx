"use client"

import { useLayoutEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { getToken } from "@/lib/auth"

/**
 * Gates children until a JWT is present in localStorage, then redirects guests to `/login`.
 * Use in a route-group layout for pages that require sign-in (JWT is client-only, so this is client-side).
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [allowed, setAllowed] = useState(false)

  useLayoutEffect(() => {
    if (!getToken()) {
      router.replace("/login")
      return
    }
    setAllowed(true)
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
