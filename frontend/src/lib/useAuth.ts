"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

/**
 * Shared auth guard + session restoration.
 *
 * On a full page refresh the Zustand `user` is reset to null while the token
 * survives in localStorage. Previously nothing re-fetched the user, so headers
 * rendered an empty username until the next login. This hook calls `getMe`
 * whenever we have a token but no user, and redirects to /login when there is
 * no token at all.
 *
 * @returns `ready` becomes true once the auth state is resolved. Pages should
 *   gate their data fetching on `ready` (and `token`) so requests are only
 *   sent after the session has been restored.
 */
export function useAuth() {
  const router = useRouter();
  const token = useStore((s) => s.token);
  const user = useStore((s) => s.user);
  const setUser = useStore((s) => s.setUser);
  const logout = useStore((s) => s.logout);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    if (!token) {
      router.replace("/login");
      return;
    }

    if (user) {
      setReady(true);
      return;
    }

    api
      .getMe()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setReady(true);
      })
      .catch(() => {
        if (cancelled) return;
        // Token invalid/expired — the 401 interceptor also handles redirect,
        // but clear local state defensively and bounce to login.
        logout();
        router.replace("/login");
      });

    return () => {
      cancelled = true;
    };
  }, [token, user, setUser, logout, router]);

  return { token, user, ready };
}
