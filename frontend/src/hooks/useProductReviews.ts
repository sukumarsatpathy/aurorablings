import { useQuery } from '@tanstack/react-query';
import reviewsService, { type ReviewSort } from '@/services/api/reviews';

export function useProductReviews(productId: string | undefined, sort: ReviewSort, page: number, pageSize = 10) {
  return useQuery({
    queryKey: ['product-reviews', productId, sort, page, pageSize],
    queryFn: () => reviewsService.listProductReviews(productId as string, { sort, page, page_size: pageSize }),
    enabled: Boolean(productId),
    staleTime: 60 * 1000,
  });
}
