"use client"

import { useMemo, useState } from "react"
import { ChevronRightIcon } from "lucide-react"

import { cn } from "@/lib/utils"

import { WorkspaceFileIcon } from "./file-icon"

type ChangedFilesSummaryProps = {
  changedPaths: string[]
  current: Map<string, string>
  original: Map<string, string>
  onSelect: (path: string) => void
}

type Stat = { path: string; additions: number; deletions: number }

export function WorkspaceChangedFilesSummary({
  changedPaths,
  current,
  original,
  onSelect,
}: ChangedFilesSummaryProps) {
  const [isOpen, setIsOpen] = useState(true)

  const stats = useMemo<Stat[]>(() => {
    const out: Stat[] = []
    for (const path of changedPaths) {
      const before = original.get(path) ?? ""
      const after = current.get(path) ?? ""
      const beforeLines = before ? before.split("\n").length : 0
      const afterLines = after ? after.split("\n").length : 0
      out.push({
        path,
        additions: Math.max(0, afterLines - beforeLines),
        deletions: Math.max(0, beforeLines - afterLines),
      })
    }
    return out.sort((a, b) => a.path.localeCompare(b.path))
  }, [changedPaths, current, original])

  if (stats.length === 0) return null

  const totalAdds = stats.reduce((s, x) => s + x.additions, 0)
  const totalDels = stats.reduce((s, x) => s + x.deletions, 0)

  return (
    <div className="border-t bg-sidebar text-sidebar-foreground">
      <button
        type="button"
        onClick={() => setIsOpen(v => !v)}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronRightIcon
          className={cn("size-3 transition-transform", isOpen && "rotate-90")}
        />
        <span className="font-semibold">
          {stats.length} File{stats.length === 1 ? "" : "s"} Changed
        </span>
        <span className="ml-auto flex items-center gap-2 text-[10px]">
          {totalAdds > 0 ? <span className="text-green-600 dark:text-green-400">+{totalAdds}</span> : null}
          {totalDels > 0 ? <span className="text-red-600 dark:text-red-400">-{totalDels}</span> : null}
        </span>
      </button>
      {isOpen ? (
        <div className="pb-1">
          {stats.map(stat => {
            const name = stat.path.split("/").pop() ?? stat.path
            return (
              <button
                type="button"
                key={stat.path}
                onClick={() => onSelect(stat.path)}
                className="flex w-full items-center gap-2 px-3 py-1 text-xs hover:bg-accent hover:text-accent-foreground"
              >
                <WorkspaceFileIcon name={name} type="file" />
                <span className="truncate font-mono">{stat.path}</span>
                <span className="ml-auto flex items-center gap-1.5 text-[10px]">
                  {stat.additions > 0 ? (
                    <span className="text-green-600 dark:text-green-400">+{stat.additions}</span>
                  ) : null}
                  {stat.deletions > 0 ? (
                    <span className="text-red-600 dark:text-red-400">-{stat.deletions}</span>
                  ) : null}
                </span>
              </button>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
