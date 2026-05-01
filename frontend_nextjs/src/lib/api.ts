/**
 * API base URL (no trailing slash).
 * - Empty / unset: same-origin `/api/v1/...` — proxied by `app/api/v1/[...path]/route.ts` (and rewrites) to FastAPI.
 * - Absolute URL: call the API directly (backend must allow CORS for the app origin).
 */
function resolveApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) return "";
  return raw.replace(/\/+$/, "");
}

export const apiBaseUrl = resolveApiBaseUrl();

/** Token endpoint path. Matches FastAPI `POST .../auth/token` (OAuth2PasswordRequestForm). */
const authTokenPath =
  process.env.NEXT_PUBLIC_AUTH_TOKEN_PATH ?? "/api/v1/auth/token";

/** Current user path. Matches FastAPI `GET .../auth/me` (Bearer JWT). */
const authMePath =
  process.env.NEXT_PUBLIC_AUTH_ME_PATH ?? "/api/v1/auth/me";

export const authTokenKey = "auth_token";

export const authApi = {
  token: `${apiBaseUrl}${authTokenPath}`,
  me: `${apiBaseUrl}${authMePath}`,
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

export async function fetchCurrentUser(
  accessToken: string,
): Promise<FetchCurrentUserResult> {
  const token = accessToken.trim();
  if (!token) {
    return { user: null, unauthorized: true };
  }

  let res: Response;
  try {
    res = await fetch(authApi.me, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
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

export function sidebarDisplayName(user: CurrentUser): string {
  const d = user.display_name?.trim();
  if (d) return d;
  const local = user.email.split("@")[0];
  return local || user.email;
}

export type LoginResult =
  | { ok: true; accessToken: string }
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
  if (res.status === 422) return "Check your email and password format";
  return `Login failed (${res.status})`;
}

/**
 * Human-readable error for authenticated fetches (chat, etc.).
 * Avoids login-specific 401 copy from {@link parseFastApiDetail}.
 */
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
    return "Not signed in or session expired. Log out and sign in again (tokens expire; SECRET_KEY changes invalidate old JWTs).";
  }
  if (res.status === 403) {
    return "You do not have permission for this action.";
  }
  if (res.status === 502 || res.status === 504) {
    return "Gateway error talking to the API. Rebuild the web image with the latest code and ensure BACKEND_PROXY_TARGET=http://api:8000 on the web container.";
  }
  return `Request failed (${res.status})`;
}

/**
 * Credential login against the FastAPI OAuth2 token endpoint (`username` = email, `password`).
 */
export async function loginWithPassword(
  email: string,
  password: string,
): Promise<LoginResult> {
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
      cache: "no-store",
    });
  } catch {
    return {
      ok: false,
      message: apiBaseUrl
        ? `Cannot reach API at ${apiBaseUrl}. Is the backend running?`
        : "Cannot reach the API (Next proxy to backend failed). Is FastAPI running on BACKEND_PROXY_TARGET (default http://127.0.0.1:8000)?",
      status: 0,
    };
  }

  if (!res.ok) {
    const message = await parseFastApiDetail(res);
    return { ok: false, message, status: res.status };
  }

  const data = (await res.json()) as {
    access_token?: string;
    token_type?: string;
  };
  if (!data.access_token) {
    return {
      ok: false,
      message: "Invalid response: missing access_token",
      status: res.status,
    };
  }
  return { ok: true, accessToken: data.access_token };
}
