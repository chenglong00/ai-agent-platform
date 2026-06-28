"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"

import { NavProjects } from "@/components/nav-projects"
import { NavMain } from "@/components/nav-main"
import { NavSecondary } from "@/components/nav-secondary"
import { NavChats, type NavChatItem } from "@/components/nav-chats"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"
import { SquarePenIcon, ChartBarIcon, FolderIcon, UsersIcon, CameraIcon, FileTextIcon, CircleHelpIcon, SearchIcon, DatabaseIcon, FileChartColumnIcon, SparklesIcon, LayoutDashboard } from "lucide-react"
import {
  fetchCurrentUser,
  sidebarDisplayName,
} from "@/lib/api"
import { getToken, logout } from "@/lib/auth"
import {
  CHAT_CONVERSATIONS_PAGE_SIZE,
  CHAT_CONVERSATIONS_UPDATED_EVENT,
  fetchChatConversations,
  type ChatConversation,
} from "@/lib/chat"

const data = {
  navMain: [
    {
      title: "Dashboard",
      url: "/dashboard",
      icon: (
        <LayoutDashboard
        />
      ),
    },
    {
      title: "New Chat",
      url: "/chat?new=1",
      icon: (
        <SquarePenIcon
        />
      ),
    },
    {
      title: "Search Chats",
      url: "#",
      icon: (
        <SearchIcon
        />
      ),
    },
    {
      title: "Analytics",
      url: "#",
      icon: (
        <ChartBarIcon
        />
      ),
    },
    {
      title: "Workspace",
      url: "/workspace",
      icon: (
        <FolderIcon
        />
      ),
    },
    {
      title: "Team",
      url: "#",
      icon: (
        <UsersIcon
        />
      ),
    },
  ],
  navClouds: [
    {
      title: "Capture",
      icon: (
        <CameraIcon
        />
      ),
      isActive: true,
      url: "#",
      items: [
        {
          title: "Active Proposals",
          url: "#",
        },
        {
          title: "Archived",
          url: "#",
        },
      ],
    },
    {
      title: "Proposal",
      icon: (
        <FileTextIcon
        />
      ),
      url: "#",
      items: [
        {
          title: "Active Proposals",
          url: "#",
        },
        {
          title: "Archived",
          url: "#",
        },
      ],
    },
    {
      title: "Prompts",
      icon: (
        <FileTextIcon
        />
      ),
      url: "#",
      items: [
        {
          title: "Active Proposals",
          url: "#",
        },
        {
          title: "Archived",
          url: "#",
        },
      ],
    },
  ],
  navSecondary: [
    {
      title: "Get Help",
      url: "#",
      icon: (
        <CircleHelpIcon
        />
      ),
    },
  ],
  projects: [
    {
      name: "Knowledge Base",
      url: "/knowledge-base",
      icon: (
        <DatabaseIcon
        />
      ),
    },
    {
      name: "Skills",
      url: "#",
      icon: (
        <SparklesIcon
        />
      ),
    },
    {
      name: "Reports",
      url: "#",
      icon: (
        <FileChartColumnIcon
        />
      ),
    },
  ],
}

const defaultBrandName =
  process.env.NEXT_PUBLIC_APP_NAME?.trim() || "Acme Inc."

/** Served from `public/logo.png` */
const defaultBrandLogo = (
  <img
    src="/logo.png"
    alt=""
    width={20}
    height={20}
    className="size-5 shrink-0 object-contain"
  />
)

export type AppSidebarProps = React.ComponentProps<typeof Sidebar> & {
  /** Shown next to the logo (default: `NEXT_PUBLIC_APP_NAME` or "Acme Inc."). */
  brandName?: string
  /** Where the header link goes (default: `/dashboard`). */
  brandHref?: string
  /** Icon or image node. Default: `/logo.png` from `public/logo.png`. */
  brandLogo?: React.ReactNode
  /** Open chat id for highlighting the Chats row (chat page only). */
  activeChatConversationId?: string | null
}

export function AppSidebar({
  brandName = defaultBrandName,
  brandHref = "/dashboard",
  brandLogo,
  activeChatConversationId = null,
  ...props
}: AppSidebarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const { state } = useSidebar()
  const [navChats, setNavChats] = React.useState<NavChatItem[]>([])
  const [navChatsLoading, setNavChatsLoading] = React.useState(false)
  const [navChatsHasMore, setNavChatsHasMore] = React.useState(false)
  const [navChatsLoadingMore, setNavChatsLoadingMore] = React.useState(false)
  const navChatsRef = React.useRef<NavChatItem[]>([])
  const navChatsHasMoreRef = React.useRef(false)

  React.useEffect(() => {
    navChatsRef.current = navChats
  }, [navChats])

  React.useEffect(() => {
    navChatsHasMoreRef.current = navChatsHasMore
  }, [navChatsHasMore])

  const toNavChatItems = React.useCallback(
    (list: ChatConversation[]): NavChatItem[] =>
      list.map(c => ({
        id: c.id,
        name: c.name,
        href: `/chat?c=${encodeURIComponent(c.id)}`,
      })),
    [],
  )
  const [navUser, setNavUser] = React.useState<{
    name: string
    email: string
    avatar?: string
  } | null>(null)

  const loadNavChatsReset = React.useCallback(async () => {
    const token = getToken()
    if (!token) {
      setNavChats([])
      setNavChatsHasMore(false)
      setNavChatsLoading(false)
      return
    }
    setNavChatsLoading(true)
    try {
      const { items, hasMore } = await fetchChatConversations(token, {
        limit: CHAT_CONVERSATIONS_PAGE_SIZE,
        offset: 0,
      })
      setNavChats(toNavChatItems(items))
      setNavChatsHasMore(hasMore)
    } catch {
      setNavChats([])
      setNavChatsHasMore(false)
    } finally {
      setNavChatsLoading(false)
    }
  }, [toNavChatItems])

  const loadNavChatsMore = React.useCallback(async () => {
    const token = getToken()
    if (
      !token ||
      !navChatsHasMoreRef.current ||
      navChatsLoadingMore ||
      navChatsLoading
    ) {
      return
    }
    setNavChatsLoadingMore(true)
    try {
      const { items, hasMore } = await fetchChatConversations(token, {
        limit: CHAT_CONVERSATIONS_PAGE_SIZE,
        offset: navChatsRef.current.length,
      })
      setNavChats(prev => [...prev, ...toNavChatItems(items)])
      setNavChatsHasMore(hasMore)
    } catch {
      /* keep list */
    } finally {
      setNavChatsLoadingMore(false)
    }
  }, [navChatsLoadingMore, navChatsLoading, toNavChatItems])

  React.useEffect(() => {
    void loadNavChatsReset()
  }, [loadNavChatsReset, pathname])

  React.useEffect(() => {
    const onUpdate = () => void loadNavChatsReset()
    window.addEventListener(CHAT_CONVERSATIONS_UPDATED_EVENT, onUpdate)
    return () =>
      window.removeEventListener(CHAT_CONVERSATIONS_UPDATED_EVENT, onUpdate)
  }, [loadNavChatsReset])

  React.useEffect(() => {
    const token = getToken()
    if (!token) return

    let cancelled = false
    void fetchCurrentUser(token).then(result => {
      if (cancelled) return
      if (!result.user) {
        if (result.unauthorized) {
          logout()
          router.replace("/login")
          return
        }
        setNavUser({
          name: "User",
          email: "Could not load profile",
          avatar: "",
        })
        return
      }
      setNavUser({
        name: sidebarDisplayName(result.user),
        email: result.user.email,
        avatar: "",
      })
    })

    return () => {
      cancelled = true
    }
  }, [router])

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="gap-2">
        <div className="flex items-center gap-2 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:items-stretch">
          <SidebarMenu className="min-w-0 flex-1 group-data-[collapsible=icon]:flex-none">
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                tooltip={brandName}
                className="data-[slot=sidebar-menu-button]:p-1.5!"
              >
                <Link href={brandHref}>
                  {brandLogo ?? defaultBrandLogo}
                  <span className="truncate text-base font-semibold">
                    {brandName}
                  </span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          <SidebarTrigger
            className="shrink-0 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:w-full"
            title={
              state === "expanded"
                ? "Collapse to icons"
                : "Expand sidebar"
            }
          />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
        <NavProjects items={data.projects} />
        <NavChats
          items={navChats}
          loading={navChatsLoading}
          activeConversationId={activeChatConversationId}
          hasMore={navChatsHasMore}
          loadingMore={navChatsLoadingMore}
          onShowMore={() => void loadNavChatsMore()}
        />
        <NavSecondary items={data.navSecondary} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        {navUser != null && typeof navUser.email === "string" ? (
          <NavUser user={navUser} />
        ) : (
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" disabled className="animate-pulse">
                <div className="size-8 rounded-lg bg-muted" />
                <div className="grid flex-1 gap-1 text-left">
                  <div className="h-4 w-24 rounded bg-muted" />
                  <div className="h-3 w-32 rounded bg-muted" />
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        )}
      </SidebarFooter>
    </Sidebar>
  )
}
