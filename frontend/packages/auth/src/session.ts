import {
  ApiError,
  getSession,
  type LanguageEnum,
  login,
  type Login,
  logout,
  type RoleEnum,
  type Session,
  setLanguage,
} from "@frutti/api";
import {
  MutationCache,
  QueryCache,
  QueryClient,
  type QueryKey,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

export type Role = RoleEnum;
export type { Session };

const SESSION_KEY = ["session"] as const;

async function fetchSession(): Promise<Session | null> {
  try {
    return await getSession();
  } catch (error) {
    // 401: nobody is logged in. 403: logged in but without an active role. Both mean "no session".
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
}

/**
 * The query client of an app. Any answer saying "not logged in" (401) or "not allowed" (403) makes it read
 * the session again: the session may have ended, or been replaced by a login to another account in
 * another tab of the same site. The route guard then shows the login screen or the wrong-app notice
 * instead of a page whose requests all fail.
 */
export function createQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error, query) => recheckSession(error, query.queryKey) }),
    mutationCache: new MutationCache({ onError: (error) => recheckSession(error) }),
  });
  function recheckSession(error: unknown, queryKey?: QueryKey) {
    if (queryKey?.[0] === SESSION_KEY[0]) return;
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      void queryClient.invalidateQueries({ queryKey: SESSION_KEY });
    }
  }
  return queryClient;
}

/** The current session: `undefined` while loading, `null` when logged out. */
export function useSession() {
  return useQuery({ queryKey: SESSION_KEY, queryFn: fetchSession, staleTime: 5 * 60 * 1000, retry: false });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: Login) => login(credentials),
    onSuccess: (session) => queryClient.setQueryData(SESSION_KEY, session),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => logout(),
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
    mutationFn: (language: LanguageEnum) => setLanguage({ language }),
    onSuccess: (session) => queryClient.setQueryData(SESSION_KEY, session),
  });
}
