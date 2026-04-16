import React, { useRef } from 'react';
import CtaButton from '../../ui/CtaButton/CtaButton';
import OptimizedImage from '@/components/ui/OptimizedImage';
import styles from './PromoBannerCard.module.css';

const clamp = (value, fallback) => {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return fallback;
  return Math.max(0, Math.min(100, parsed));
};

const PromoBannerCard = ({ banner, size = 'default', className = '' }) => {
  const cardRef = useRef(null);
  const bgColor = banner.bg_color || '#f5f0eb';

  const titleColor = banner.title_color || '#1a1a1a';
  const subtitleColor = banner.subtitle_color || titleColor;
  const badgeColor = banner.badge_color || titleColor;
  const ctaTextColor = banner.cta_text_color || titleColor;
  const ctaBorderColor = banner.cta_border_color || ctaTextColor;
  const bannerSrc = banner.image_large || banner.image || '';
  const bannerSrcSet = [
    banner.image_small ? `${banner.image_small} 480w` : '',
    banner.image_medium ? `${banner.image_medium} 768w` : '',
    (banner.image_large || banner.image) ? `${banner.image_large || banner.image} 1200w` : '',
  ].filter(Boolean).join(', ');

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
      style={{ backgroundColor: bgColor }}
    >
      <div className={styles.imageWrapper}>
        {bannerSrc ? (
          <OptimizedImage
            src={bannerSrc}
            srcSet={bannerSrcSet || undefined}
            sizes="(max-width: 768px) 100vw, 1200px"
            alt={banner.title || 'Promotional banner'}
            className={styles.image}
            loading="lazy"
            decoding="async"
            width={1200}
            height={700}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div
            className={styles.image}
            style={{
              backgroundColor: bgColor || '#f5f0eb',
              width: '100%',
              height: '100%',
            }}
          />
        )}
        {bannerSrc && <div className={styles.overlay} />}
      </div>

      <div className={styles.contentOverlay}>
        {!!banner.badge_bold && (
          <span
            className={styles.badgeBold}
            style={{
              left: `${clamp(banner.badge_bold_x, 8)}%`,
              top: `${clamp(banner.badge_bold_y, 22)}%`,
              color: badgeColor,
            }}
          >
            {banner.badge_bold}
          </span>
        )}
        {!!banner.badge_text && (
          <span
            className={styles.badgeText}
            style={{
              left: `${clamp(banner.badge_text_x, 22)}%`,
              top: `${clamp(banner.badge_text_y, 22)}%`,
              color: badgeColor,
            }}
          >
            {banner.badge_text}
          </span>
        )}

        {!!banner.title && (
          <h3
            className={styles.title}
            style={{
              left: `${clamp(banner.title_x, 8)}%`,
              top: `${clamp(banner.title_y, 46)}%`,
              color: titleColor,
            }}
          >
            {banner.title}
          </h3>
        )}

        {!!banner.subtitle && (
          <p
            className={styles.subtitle}
            style={{
              left: `${clamp(banner.subtitle_x, 8)}%`,
              top: `${clamp(banner.subtitle_y, 64)}%`,
              color: subtitleColor,
            }}
          >
            {banner.subtitle}
          </p>
        )}

        {!!banner.cta_label && (
          <CtaButton
            label={banner.cta_label}
            to={banner.cta_url || '#'}
            className={styles.cta}
            style={{
              left: `${clamp(banner.cta_x, 8)}%`,
              top: `${clamp(banner.cta_y, 80)}%`,
              color: ctaTextColor,
              borderBottomColor: ctaBorderColor,
              marginTop: 0,
            }}
          />
        )}
      </div>
    </div>
  );
};

export default PromoBannerCard;
