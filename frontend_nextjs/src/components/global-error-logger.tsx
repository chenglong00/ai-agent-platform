"use client"

import { useEffect } from "react"

/** Registers `window.onerror` once in the browser (not during SSR). */
export function GlobalErrorLogger() {
  useEffect(() => {
    window.onerror = function (msg, url, line, col, error) {
      console.error("Global error:", { msg, url, line, col, error })
    }
    return () => {
      window.onerror = null
    }
  }, [])
  return null
}
