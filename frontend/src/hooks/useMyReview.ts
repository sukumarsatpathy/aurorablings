import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import reviewsService from '@/services/api/reviews';

export function useMyReview(productId: string | undefined) {
  const token = localStorage.getItem('auth_token');

  const query = useQuery({
    queryKey: ['my-reviews', productId],
    queryFn: () => reviewsService.listMyReviews({ page: 1, page_size: 100 }),
    enabled: Boolean(token && productId),
    staleTime: 60 * 1000,
  });

  const myReview = useMemo(() => {
    if (!query.data?.data || !productId) return null;
    return query.data.data.find((review) => review.product === productId) || null;
  }, [productId, query.data?.data]);

  return {
    ...query,
    myReview,
  };
}
