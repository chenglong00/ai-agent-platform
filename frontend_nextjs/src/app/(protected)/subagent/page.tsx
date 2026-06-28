"use client"

import { Bot } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

export default function SubAgentPage() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Bot className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">SubAgent</h1>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 lg:p-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Configure sub-agents</CardTitle>
              <CardDescription>
                Define specialized agents the deep agent can delegate tasks to.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                SubAgent management is coming soon.
              </p>
            </CardContent>
          </Card>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
