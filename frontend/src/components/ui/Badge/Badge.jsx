import React from 'react';
import styles from './Badge.module.css';

/**
 * Props: boldText (string), normalText (string), className (optional)
 * Renders: <span><strong>50%</strong> off select silver ring</span>
 */
const Badge = ({ boldText, normalText, className = '' }) => {
  return (
    <span className={`${styles.badge} ${className}`}>
      {boldText && <strong>{boldText} </strong>}
      {normalText}
    </span>
  );
};

export default Badge;
