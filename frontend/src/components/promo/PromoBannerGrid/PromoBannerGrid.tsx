import type { FC } from 'react';
import PromoBannerGridJs from './PromoBannerGrid.jsx';
import type { PromoBanner } from '@/types/promo';

export interface PromoBannerGridProps {
  banners?: PromoBanner[];
  previewMode?: boolean;
}

const PromoBannerGrid = PromoBannerGridJs as FC<PromoBannerGridProps>;

export default PromoBannerGrid;
