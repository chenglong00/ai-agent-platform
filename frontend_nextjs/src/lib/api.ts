/**
 * API base URL (no trailing slash).
 * - Empty / unset: same-origin `/api/v1/...` — proxied by Next to FastAPI (cookies work).
 * - Absolute URL: call the API directly (backend must allow CORS with credentials).
 */
function resolveApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) return "";
  return raw.replace(/\/+$/, "");
}

export const apiBaseUrl = resolveApiBaseUrl();

const authTokenPath =
  process.env.NEXT_PUBLIC_AUTH_TOKEN_PATH ?? "/api/v1/auth/token";

const authMePath =
  process.env.NEXT_PUBLIC_AUTH_ME_PATH ?? "/api/v1/auth/me";

/** @deprecated Tokens are httpOnly cookies; kept for legacy call sites that pass an optional Bearer override. */
export const authTokenKey = "auth_token";

export const authApi = {
  token: `${apiBaseUrl}${authTokenPath}`,
  register: `${apiBaseUrl}/api/v1/auth/register`,
  refresh: `${apiBaseUrl}/api/v1/auth/refresh`,
  logout: `${apiBaseUrl}/api/v1/auth/logout`,
  me: `${apiBaseUrl}${authMePath}`,
  wsToken: `${apiBaseUrl}/api/v1/auth/ws-token`,
};

export const oauthUrls = {
  google: `${apiBaseUrl}/api/v1/oauth/google`,
};

/** Matches FastAPI `UserResponse` from `GET /api/v1/auth/me`. */
export type CurrentUser = {
  id: string;
  email: string;
  display_name?: string | null;
  role?: string;
  is_approved?: boolean;
  is_active?: boolean;
  created_at?: string | null;
};

export type FetchCurrentUserResult =
  | { user: CurrentUser }
  | { user: null; unauthorized: boolean };

/** Build fetch init with session cookies (optional Bearer override for WebSocket helpers). */
export function apiFetchInit(
  init: RequestInit = {},
  accessToken?: string | null,
): RequestInit {
  const headers = new Headers(init.headers);
  if (accessToken?.trim()) {
    headers.set("Authorization", `Bearer ${accessToken.trim()}`);
  }
  return {
    ...init,
    credentials: "include",
    cache: init.cache ?? "no-store",
    headers,
  };
}

export async function refreshSession(): Promise<boolean> {
  try {
    const res = await fetch(authApi.refresh, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function authorizedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  accessToken?: string | null,
): Promise<Response> {
  let res = await fetch(input, apiFetchInit(init, accessToken));
  if (res.status === 401 && !accessToken?.trim()) {
    const refreshed = await refreshSession();
    if (refreshed) {
      res = await fetch(input, apiFetchInit(init, accessToken));
    }
  }
  return res;
}

export async function fetchCurrentUser(
  accessToken?: string | null,
): Promise<FetchCurrentUserResult> {
  let res: Response;
  try {
    res = await authorizedFetch(authApi.me, { method: "GET" }, accessToken);
  } catch {
    return { user: null, unauthorized: false };
  }

  if (res.status === 401 || res.status === 403) {
    return { user: null, unauthorized: true };
  }
  if (!res.ok) {
    return { user: null, unauthorized: false };
  }

  try {
    const user = (await res.json()) as CurrentUser;
    if (!user?.email) {
      return { user: null, unauthorized: false };
    }
    return { user };
  } catch {
    return { user: null, unauthorized: false };
  }
}

export async function fetchWsToken(): Promise<string | null> {
  try {
    const res = await authorizedFetch(authApi.wsToken, { method: "GET" });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token?: string };
    return data.access_token?.trim() || null;
  } catch {
    return null;
  }
}

export function sidebarDisplayName(user: CurrentUser): string {
  const d = user.display_name?.trim();
  if (d) return d;
  const local = user.email.split("@")[0];
  return local || user.email;
}

export type AuthActionResult =
  | { ok: true }
  | { ok: false; message: string; status: number };

export async function parseFastApiDetail(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | string | undefined;
      if (first && typeof first === "object" && "msg" in first) {
        return String(first.msg);
      }
      if (typeof first === "string") return first;
    }
  } catch {
    /* ignore */
  }
  if (res.status === 401) return "Invalid email or password";
  if (res.status === 409) return "An account with this email already exists";
  if (res.status === 422) return "Check your email and password format";
  return `Request failed (${res.status})`;
}

export async function parseApiErrorMessage(res: Response): Promise<string> {
  const raw = await res.text();
  let detail: unknown;
  try {
    detail = (JSON.parse(raw) as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | string | undefined;
    if (first && typeof first === "object" && "msg" in first) {
      return String(first.msg);
    }
    if (typeof first === "string") return first;
  }
  if (res.status === 401) {
    return "Not signed in or session expired. Please sign in again.";
  }
  if (res.status === 403) {
    return "You do not have permission for this action.";
  }
  if (res.status === 502 || res.status === 504) {
    return "Gateway error talking to the API.";
  }
  return `Request failed (${res.status})`;
}

export async function loginWithPassword(
  email: string,
  password: string,
): Promise<AuthActionResult> {
  const body = new URLSearchParams({
    username: email.trim(),
    password,
    grant_type: "password",
  });

  let res: Response;
  try {
    res = await fetch(authApi.token, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    return {
      ok: false,
      message: apiBaseUrl
        ? `Cannot reach API at ${apiBaseUrl}. Is the backend running?`
        : "Cannot reach the API. Is FastAPI running?",
      status: 0,
    };
  }

  if (!res.ok) {
    const message = await parseFastApiDetail(res);
    return { ok: false, message, status: res.status };
  }
  return { ok: true };
}

export async function registerWithPassword(
  email: string,
  password: string,
  displayName?: string | null,
): Promise<AuthActionResult> {
  let res: Response;
  try {
    res = await fetch(authApi.register, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.trim(),
        password,
        display_name: displayName?.trim() || null,
      }),
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    return {
      ok: false,
      message: "Cannot reach the API. Is the backend running?",
      status: 0,
    };
  }

  if (!res.ok) {
    const message = await parseFastApiDetail(res);
    return { ok: false, message, status: res.status };
  }
  return { ok: true };
}

export async function logoutSession(): Promise<void> {
  try {
    await fetch(authApi.logout, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    /* best effort */
  }
}
