import { useState, useEffect } from 'react';
import { bannersApi } from '../api/bannersApi';

/**
 * Hook for fetching active promotional banners.
 * Returns: { banners, loading, error }
 */
export const usePromoBanners = () => {
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
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
  }, []);

  return { banners, loading, error };
};
