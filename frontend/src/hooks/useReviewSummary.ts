import { useQuery } from '@tanstack/react-query';
import reviewsService from '@/services/api/reviews';

export function useReviewSummary(productId: string | undefined) {
  return useQuery({
    queryKey: ['review-summary', productId],
    queryFn: () => reviewsService.getReviewSummary(productId as string),
    enabled: Boolean(productId),
    staleTime: 60 * 1000,
  });
}
