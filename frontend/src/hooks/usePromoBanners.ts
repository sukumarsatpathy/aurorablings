import { usePromoBanners as usePromoBannersJs } from './usePromoBanners.js';
import type { PromoBanner } from '@/types/promo';

export interface UsePromoBannersResult {
  banners: PromoBanner[];
  loading: boolean;
  error: unknown;
}

export const usePromoBanners = (): UsePromoBannersResult =>
  usePromoBannersJs() as UsePromoBannersResult;
