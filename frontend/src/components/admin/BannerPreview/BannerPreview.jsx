import React from 'react';
import PromoBannerGrid from '../../promo/PromoBannerGrid/PromoBannerGrid';
import styles from './BannerPreview.module.css';

/**
 * Props: banners (array of PromoBanner objects)
 */
const BannerPreview = ({ banners }) => {
  return (
    <div className={styles.previewContainer}>
      <h3 className={styles.label}>Live Preview</h3>
      <div className={styles.scaler}>
        <div className={styles.wrapper}>
          <PromoBannerGrid banners={banners} previewMode={true} />
        </div>
      </div>
      <p className={styles.note}>Changes are shown here in real-time before saving.</p>
    </div>
  );
};

export default BannerPreview;
