"use client"

import { Plug } from "lucide-react"

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

export default function ConnectorPage() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Plug className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">Connector</h1>
        </header>

        <div className="flex flex-1 flex-col gap-4 p-4 lg:p-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Connect external services</CardTitle>
              <CardDescription>
                Configure integrations that the deep agent can use at runtime.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Connector management is coming soon.
              </p>
            </CardContent>
          </Card>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
