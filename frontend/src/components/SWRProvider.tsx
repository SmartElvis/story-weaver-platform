"use client";

import { SWRConfig } from "swr";

/**
 * Global SWR configuration. Individual hooks pass an explicit fetcher
 * (a closure over the typed `api` client), so this only sets shared behavior.
 * revalidateOnFocus is disabled to avoid surprising refetches while editing.
 */
export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        shouldRetryOnError: false,
      }}
    >
      {children}
    </SWRConfig>
  );
}
