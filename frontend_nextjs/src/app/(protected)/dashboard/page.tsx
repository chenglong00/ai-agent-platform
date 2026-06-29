"use client"

import { AppSidebar } from "@/components/app-sidebar"
import { ChartAreaInteractive } from "@/components/chart-area-interactive"
import { DataTable } from "@/components/data-table"
import { SectionCards } from "@/components/section-cards"
import { SiteHeader } from "@/components/site-header"
import { WorkspaceChatPanel } from "@/components/workspace/chat-panel"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

import data from "./data.json"

export default function Page() {
  return (
    <SidebarProvider
      className="h-svh min-h-0 overflow-hidden"
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <AppSidebar variant="inset" />
      <SidebarInset className="min-h-0 overflow-hidden">
        <SiteHeader />
        <ResizablePanelGroup
          direction="horizontal"
          autoSaveId="dashboard-layout"
          className="min-h-0 flex-1 overflow-hidden"
        >
          <ResizablePanel
            defaultSize={75}
            minSize={40}
            className="flex min-h-0 flex-col"
          >
            <div className="min-h-0 flex-1 overflow-y-auto">
              <div className="@container/main flex flex-col gap-2">
                <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
                  <SectionCards />
                  <div className="px-4 lg:px-6">
                    <ChartAreaInteractive />
                  </div>
                  <DataTable data={data} />
                </div>
              </div>
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel
            defaultSize={25}
            minSize={18}
            maxSize={50}
            className="flex min-h-0 flex-col"
          >
            <WorkspaceChatPanel variant="dashboard" />
          </ResizablePanel>
        </ResizablePanelGroup>
      </SidebarInset>
    </SidebarProvider>
  )
}
