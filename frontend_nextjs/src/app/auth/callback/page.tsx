"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

/**
 * Legacy OAuth callback landing page. New flow sets httpOnly cookies on the
 * backend redirect; this page handles old ?token= links and forwards to dashboard.
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const legacyToken = searchParams.get("token");
    if (legacyToken) {
      console.warn(
        "OAuth token in URL is deprecated; ensure GOOGLE_REDIRECT_URI uses the Next proxy and cookies are enabled.",
      );
    }
    router.replace("/dashboard");
  }, [router, searchParams]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <p className="text-muted-foreground">Signing you in…</p>
    </div>
  );
}
