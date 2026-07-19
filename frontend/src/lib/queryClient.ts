import { QueryClient } from '@tanstack/react-query';

/**
 * Shared React Query client.
 *
 * The defaults below replace React Query's own, which are tuned for
 * real-time dashboards rather than a catalog:
 *   - staleTime 0            -> every component mount refetched
 *   - refetchOnWindowFocus   -> alt-tabbing back refired every active query
 *   - retry 3                -> a failing endpoint was hit 4x before erroring
 *
 * Individual hooks can still override per call (several already set their
 * own staleTime, e.g. useBranding, useProductReviews).
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Catalog data is not real-time; 5 minutes of freshness is plenty.
      staleTime: 5 * 60 * 1000,
      // Keep unused data around so back-navigation is instant.
      gcTime: 30 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      retry: 1,
    },
    mutations: {
      // Deliberately 0. A write that times out at the gateway may still have
      // succeeded server-side; retrying it risks duplicate orders or payments.
      // Surface the error and let the user decide.
      retry: 0,
    },
  },
});
