import { SidebarTrigger } from "@/components/ui/sidebar"

export function SiteHeader() {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        {/* Desktop: toggle lives in the sidebar header. Mobile sheet needs a control here to reopen. */}
        <SidebarTrigger className="md:hidden" />
        <h1 className="text-base font-medium">Dashboard</h1>
      </div>
    </header>
  )
}
