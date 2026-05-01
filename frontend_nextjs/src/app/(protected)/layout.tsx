import { RequireAuth } from "@/components/require-auth"

/** `/dashboard`, `/chat`, and any future routes in this group require a stored JWT. */
export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <RequireAuth>{children}</RequireAuth>
}
