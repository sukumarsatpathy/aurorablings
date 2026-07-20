import { useState, useEffect } from 'react';
import { bannersApi } from '../api/bannersApi';
import { getBootData } from '../services/boot';

/**
 * Hook for fetching active promotional banners.
 *
 * Fast path: in production, nginx SSI injects window.__BOOT__ with the active
 * banners into index.html (see backend/apps/banners/bootstrap.py), so the
 * grid renders on first paint with zero API round trips — this is what lets
 * the server-injected LCP preload match the <img> React eventually mounts.
 * Fallback (dev server, SSI failure): fetch /banners/active/ as before.
 *
 * Returns: { banners, loading, error }
 */
export const usePromoBanners = () => {
  const bootBanners = getBootData()?.banners;
  const hasBoot = Array.isArray(bootBanners);

  const [banners, setBanners] = useState(hasBoot ? bootBanners : []);
  const [loading, setLoading] = useState(!hasBoot);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (hasBoot) return;

    const fetchBanners = async () => {
      try {
        setLoading(true);
        const data = await bannersApi.getActive();
        // Extract array from standard envelope or fallback to data itself
        const bannerList = data.data || data.results || (Array.isArray(data) ? data : []);
        setBanners(bannerList);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch promotional banners:', err);
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchBanners();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { banners, loading, error };
};
