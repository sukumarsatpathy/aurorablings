import React, { useEffect, useRef } from 'react';
import PromoBannerCard from '../PromoBannerCard/PromoBannerCard';
import styles from './PromoBannerGrid.module.css';
import { gsap } from 'gsap';

/**
 * Props: banners (array), previewMode (bool)
 */
const PromoBannerGrid = ({ banners = [], previewMode = false }) => {
  const gridRef = useRef(null);

  useEffect(() => {
    if (previewMode) return;

    const ctx = gsap.context(() => {
      gsap.fromTo('.promo-card', 
        { opacity: 0, y: 30 }, 
        { 
          opacity: 1, 
          y: 0, 
          duration: 0.8, 
          stagger: 0.15, 
          ease: 'power3.out',
          clearProps: 'all'
        }
      );
    }, gridRef);

    return () => ctx.revert();
  }, [banners, previewMode]);

  // Sort banners by position or use as is? 
  // The user specified position-based labels.
  // Let's map them to their grid spots.
  const getBannerByPosition = (pos) => banners.find(b => b.position === pos);

  const topLeft = getBannerByPosition('top-left');
  const topRight = getBannerByPosition('top-right');
  const bottomLeft = getBannerByPosition('bottom-left');
  const bottomRight = getBannerByPosition('bottom-right');

  // If no banners, show placeholders or nothing?
  if (banners.length === 0 && !previewMode) return null;

  return (
    <div ref={gridRef} className={`${styles.grid} ${previewMode ? styles.preview : ''}`}>
      <div className={`${styles.cell} ${styles.topLeft}`}>
        {topLeft && <PromoBannerCard banner={topLeft} />}
      </div>
      <div className={`${styles.cell} ${styles.topRight}`}>
        {topRight && <PromoBannerCard banner={topRight} size="tall" />}
      </div>
      <div className={`${styles.cell} ${styles.bottomLeft}`}>
        {bottomLeft && <PromoBannerCard banner={bottomLeft} size="tall" />}
      </div>
      <div className={`${styles.cell} ${styles.bottomRight}`}>
        {bottomRight && <PromoBannerCard banner={bottomRight} />}
      </div>
    </div>
  );
};

export default PromoBannerGrid;
