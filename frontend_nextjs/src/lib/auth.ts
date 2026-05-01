"use client";

import { authTokenKey } from "./api";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(authTokenKey);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(authTokenKey, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(authTokenKey);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

/** Clear stored JWT. Call then redirect to `/login` (no server session for stateless JWT). */
export function logout(): void {
  clearToken();
}
