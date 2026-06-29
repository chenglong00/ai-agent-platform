"use client";

import {
  fetchCurrentUser,
  fetchWsToken,
  logoutSession,
  refreshSession,
} from "./api";

/** @deprecated Session uses httpOnly cookies; returns null. Use fetchCurrentUser() instead. */
export function getToken(): string | null {
  return null;
}

/** @deprecated No-op; tokens are httpOnly cookies set by the backend. */
export function setToken(_token: string): void {}

/** @deprecated No-op; tokens are httpOnly cookies. */
export function clearToken(): void {}

export async function isAuthenticated(): Promise<boolean> {
  const result = await fetchCurrentUser();
  return !!result.user;
}

export async function getWsToken(): Promise<string | null> {
  return fetchWsToken();
}

/** Revoke refresh token server-side and clear auth cookies. */
export async function logout(): Promise<void> {
  await logoutSession();
}

export { refreshSession, fetchCurrentUser };
