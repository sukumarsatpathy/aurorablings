import React, { useEffect, useRef } from 'react';
import Badge from '../../ui/Badge/Badge';
import CtaButton from '../../ui/CtaButton/CtaButton';
import ImageWithFallback from '../../ui/ImageWithFallback/ImageWithFallback';
import styles from './PromoBannerCard.module.css';
import { gsap } from 'gsap';

/**
 * Props: banner (PromoBanner object)
 * Uses ImageWithFallback, Badge, CtaButton internally
 */
const PromoBannerCard = ({ banner, size = 'default', className = '' }) => {
  const cardRef = useRef(null);

  useEffect(() => {
    // Entrance animation if not in preview mode (handle simple cases)
    // The staggered animation is usually controlled by the parent Grid
  }, []);

  return (
    <div 
      ref={cardRef} 
      className={[
        styles.card,
        size === 'tall' ? styles.cardTall : '',
        size === 'short' ? styles.cardShort : '',
        className,
        'promo-card',
      ].join(' ')}
      style={{ backgroundColor: banner.bg_color }}
    >
      <div className={styles.imageWrapper}>
        <ImageWithFallback 
          src={banner.image} 
          alt={banner.title} 
          bgColor={banner.bg_color}
          className={styles.image}
        />
        {banner.image && <div className={styles.overlay} />}
      </div>
      
      <div className={styles.content}>
        {(banner.badge_bold || banner.badge_text) && (
          <Badge 
            boldText={banner.badge_bold} 
            normalText={banner.badge_text} 
            className={styles.badge}
          />
        )}
        <h3 className={styles.title}>{banner.title}</h3>
        <CtaButton 
          label={banner.cta_label} 
          to={banner.cta_url} 
          className={styles.cta}
        />
      </div>
    </div>
  );
};

export default PromoBannerCard;
