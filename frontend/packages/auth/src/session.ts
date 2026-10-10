import type { Language } from "@frutti/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch } from "./api";

export type Role = "owner" | "manager" | "driver" | "accountant";

/** Answer of `/api/v1/me`: who is logged in and what they may do. */
export interface Session {
  user: { id: number; username: string; first_name: string; last_name: string; language: Language };
  organization: { id: number; name: string };
  role: Role;
  truck: { id: number; name: string } | null;
}

const SESSION_KEY = ["session"] as const;

async function fetchSession(): Promise<Session | null> {
  try {
    return await apiFetch<Session>("/me");
  } catch (error) {
    // 401: nobody is logged in. 403: logged in but without an active role. Both mean "no session".
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
}

/** The current session: `undefined` while loading, `null` when logged out. */
export function useSession() {
  return useQuery({ queryKey: SESSION_KEY, queryFn: fetchSession, staleTime: 5 * 60 * 1000, retry: false });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      apiFetch<Session>("/auth/login", { method: "POST", body: credentials }),
    onSuccess: (session) => queryClient.setQueryData(SESSION_KEY, session),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>("/auth/logout", { method: "POST" }),
    onSuccess: () => {
      // Update the session in place so every mounted guard sees the logout at once.
      queryClient.setQueryData(SESSION_KEY, null);
      // Drop every other cached answer: the next user must never see the previous user's data.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== SESSION_KEY[0] });
    },
  });
}

/** Saves the user's language on their account; the route guard then applies it to the page. */
export function useSetLanguage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (language: Language) => apiFetch<Session>("/me", { method: "PATCH", body: { language } }),
    onSuccess: (session) => queryClient.setQueryData(SESSION_KEY, session),
  });
}
