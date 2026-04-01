import React from 'react';
import { Link } from 'react-router-dom';
import styles from './CtaButton.module.css';

/**
 * Props: label (string, default "Shop Now"), to (string URL), className (optional)
 * Renders a React Router <Link> styled as "SHOP NOW →"
 */
const CtaButton = ({ label = 'Shop Now', to = '#', className = '', style }) => {
  return (
    <Link to={to} className={`${styles.cta} ${className}`} style={style}>
      {label.toUpperCase()} <span className={styles.arrow}>→</span>
    </Link>
  );
};

export default CtaButton;
