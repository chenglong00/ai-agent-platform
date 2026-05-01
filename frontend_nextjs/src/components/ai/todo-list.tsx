"use client"

import { memo } from "react"
import { cn } from "@/lib/utils"

export type TodoItem = {
  content: string
  status: "pending" | "in_progress" | "completed"
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getStatusIcon(status: TodoItem["status"]) {
  if (status === "completed") return "✓"
  if (status === "in_progress") return "◉"
  return "○"
}

function getIconClass(status: TodoItem["status"]) {
  if (status === "completed") return "text-green-500"
  if (status === "in_progress") return "text-amber-500 animate-pulse"
  return "text-muted-foreground"
}

function getItemClass(status: TodoItem["status"]) {
  if (status === "completed") return "border-green-100 bg-green-50/50 dark:border-green-950 dark:bg-green-950/20"
  if (status === "in_progress") return "border-amber-100 bg-amber-50/50 dark:border-amber-950 dark:bg-amber-950/20"
  return "border-transparent"
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Progress</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-green-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function TodoItemRow({ todo }: { todo: TodoItem }) {
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-md border px-3 py-2",
        "transition-all duration-300 ease-in-out",
        getItemClass(todo.status),
      )}
    >
      <span className={cn("mt-0.5 shrink-0 font-mono text-base leading-none transition-colors duration-300", getIconClass(todo.status))}>
        {getStatusIcon(todo.status)}
      </span>
      <span
        className={cn(
          "text-sm transition-all duration-300",
          todo.status === "completed" ? "line-through opacity-60" : "",
        )}
      >
        {todo.content}
      </span>
    </li>
  )
}

// ── TodoList ──────────────────────────────────────────────────────────────────

type Props = {
  todos: TodoItem[]
  isLoading?: boolean
  className?: string
}

export const TodoList = memo(({ todos, isLoading = false, className }: Props) => {
  if (todos.length === 0 && !isLoading) return null

  if (todos.length === 0 && isLoading) {
    return (
      <div className={cn("rounded-lg border bg-card p-4 shadow-sm", className)}>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="inline-block animate-spin">⟳</span>
          Agent is creating a plan…
        </div>
      </div>
    )
  }

  const completed = todos.filter(t => t.status === "completed").length
  const pct = Math.round((completed / todos.length) * 100)

  return (
    <div className={cn("rounded-lg border bg-card p-4 shadow-sm space-y-4", className)}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Agent Progress</h3>
        <span className="text-xs text-muted-foreground">{completed}/{todos.length} tasks</span>
      </div>

      <ProgressBar pct={pct} />

      <ul className="space-y-2">
        {todos.map((todo, i) => (
          <TodoItemRow key={i} todo={todo} />
        ))}
      </ul>
    </div>
  )
})

TodoList.displayName = "TodoList"
