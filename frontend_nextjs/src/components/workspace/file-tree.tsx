"use client"

import { useState } from "react"
import { ChevronRightIcon, Loader2Icon } from "lucide-react"

import { cn } from "@/lib/utils"
import type { WorkspaceTreeNode } from "@/lib/workspace"

import { WorkspaceFileIcon } from "./file-icon"

type FileTreeProps = {
  nodes: WorkspaceTreeNode[]
  selectedPath: string | null
  changedPaths: Set<string>
  onSelect: (path: string) => void
  isLoading?: boolean
  emptyHint?: string
}

export function WorkspaceFileTree({
  nodes,
  selectedPath,
  changedPaths,
  onSelect,
  isLoading,
  emptyHint = "No files yet",
}: FileTreeProps) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center justify-between border-b px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <span>Explorer</span>
        {isLoading ? <Loader2Icon className="size-3 animate-spin" /> : null}
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {nodes.length === 0 && !isLoading ? (
          <div className="px-3 py-4 text-center text-xs text-muted-foreground">{emptyHint}</div>
        ) : (
          nodes.map(node => (
            <FileTreeItem
              key={node.path}
              node={node}
              depth={0}
              selectedPath={selectedPath}
              changedPaths={changedPaths}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </div>
  )
}

type FileTreeItemProps = {
  node: WorkspaceTreeNode
  depth: number
  selectedPath: string | null
  changedPaths: Set<string>
  onSelect: (path: string) => void
}

function FileTreeItem({
  node,
  depth,
  selectedPath,
  changedPaths,
  onSelect,
}: FileTreeItemProps) {
  const [isOpen, setIsOpen] = useState(depth < 1)
  const isSelected = node.path === selectedPath
  const isChanged = changedPaths.has(node.path)

  const handleClick = () => {
    if (node.type === "directory") setIsOpen(prev => !prev)
    else onSelect(node.path)
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        className={cn(
          "flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs transition-colors",
          "hover:bg-accent hover:text-accent-foreground",
          isSelected && "bg-accent text-accent-foreground",
        )}
        style={{ paddingLeft: depth * 12 + 8 }}
      >
        {node.type === "directory" ? (
          <ChevronRightIcon
            className={cn(
              "size-3 shrink-0 text-muted-foreground transition-transform",
              isOpen && "rotate-90",
            )}
          />
        ) : (
          <span className="w-3" aria-hidden />
        )}
        <WorkspaceFileIcon
          name={node.name}
          type={node.type}
          isOpen={node.type === "directory" ? isOpen : undefined}
        />
        <span className="truncate font-mono">{node.name}</span>
        {isChanged ? (
          <span
            className="ml-auto size-1.5 shrink-0 rounded-full bg-amber-500"
            aria-label="Modified"
            title="Modified during this chat session"
          />
        ) : null}
      </button>
      {node.type === "directory" && isOpen && node.children
        ? node.children.map(child => (
            <FileTreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              changedPaths={changedPaths}
              onSelect={onSelect}
            />
          ))
        : null}
    </div>
  )
}
