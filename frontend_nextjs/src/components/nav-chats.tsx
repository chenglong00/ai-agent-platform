"use client"

import Link from "next/link"
import { Loader2Icon, MessageCircleIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

export type NavChatItem = {
  id: string
  /** Conversation `name` from the API (shown as-is). */
  name: string
  href: string
}

export function NavChats({
  items,
  activeConversationId,
  loading,
  hasMore = false,
  loadingMore = false,
  onShowMore,
}: {
  items: NavChatItem[]
  activeConversationId?: string | null
  loading?: boolean
  hasMore?: boolean
  loadingMore?: boolean
  onShowMore?: () => void
}) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Chats</SidebarGroupLabel>
      <SidebarMenu>
        {loading ? (
          <SidebarMenuItem>
            <SidebarMenuButton
              disabled
              tooltip="Loading chats…"
              className="text-sidebar-foreground/70"
            >
              <Loader2Icon className="size-4 shrink-0 animate-spin" />
              <span>Loading chats…</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : items.length === 0 ? (
          <SidebarMenuItem>
            <SidebarMenuButton
              disabled
              tooltip="No chats yet"
              className="text-sidebar-foreground/70"
            >
              <MessageCircleIcon className="size-4 shrink-0 opacity-50" />
              <span className="truncate">No chats yet</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ) : (
          items.map(item => (
            <SidebarMenuItem key={item.id}>
              <SidebarMenuButton
                asChild
                tooltip={item.name}
                isActive={item.id === activeConversationId}
              >
                <Link href={item.href}>
                  <MessageCircleIcon className="size-4 shrink-0" />
                  <span className="truncate">{item.name}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))
        )}
      </SidebarMenu>
      {hasMore && items.length > 0 && !loading ? (
        <div className="px-2 pb-1 pt-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 w-full text-xs text-muted-foreground hover:text-foreground"
            disabled={loadingMore}
            onClick={() => onShowMore?.()}
          >
            {loadingMore ? (
              <>
                <Loader2Icon className="mr-1 size-3.5 shrink-0 animate-spin" />
                Loading…
              </>
            ) : (
              "Show more"
            )}
          </Button>
        </div>
      ) : null}
    </SidebarGroup>
  )
}
