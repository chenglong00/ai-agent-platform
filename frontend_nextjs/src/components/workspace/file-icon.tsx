"use client"

import {
  FileCodeIcon,
  FileIcon,
  FileImageIcon,
  FileJsonIcon,
  FileTextIcon,
  FolderIcon,
  FolderOpenIcon,
  type LucideIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"

const EXT_ICON: Record<string, LucideIcon> = {
  ts: FileCodeIcon,
  tsx: FileCodeIcon,
  js: FileCodeIcon,
  jsx: FileCodeIcon,
  mjs: FileCodeIcon,
  cjs: FileCodeIcon,
  py: FileCodeIcon,
  go: FileCodeIcon,
  rs: FileCodeIcon,
  java: FileCodeIcon,
  rb: FileCodeIcon,
  c: FileCodeIcon,
  cpp: FileCodeIcon,
  h: FileCodeIcon,
  hpp: FileCodeIcon,
  swift: FileCodeIcon,
  kt: FileCodeIcon,
  vue: FileCodeIcon,
  svelte: FileCodeIcon,
  html: FileCodeIcon,
  css: FileCodeIcon,
  scss: FileCodeIcon,
  less: FileCodeIcon,
  json: FileJsonIcon,
  md: FileTextIcon,
  txt: FileTextIcon,
  yml: FileTextIcon,
  yaml: FileTextIcon,
  toml: FileTextIcon,
  xml: FileTextIcon,
  svg: FileImageIcon,
  png: FileImageIcon,
  jpg: FileImageIcon,
  jpeg: FileImageIcon,
  gif: FileImageIcon,
  webp: FileImageIcon,
  ico: FileImageIcon,
}

type FileIconProps = {
  name: string
  type: "file" | "directory"
  isOpen?: boolean
  className?: string
}

export function WorkspaceFileIcon({ name, type, isOpen, className }: FileIconProps) {
  if (type === "directory") {
    const Icon = isOpen ? FolderOpenIcon : FolderIcon
    return <Icon className={cn("size-4 shrink-0 text-muted-foreground", className)} />
  }
  const ext = name.includes(".") ? name.split(".").pop()!.toLowerCase() : ""
  const Icon = EXT_ICON[ext] ?? FileIcon
  return <Icon className={cn("size-4 shrink-0 text-muted-foreground", className)} />
}
