import React from 'react';
import styles from './Toggle.module.css';

/**
 * Props: checked (bool), onChange (fn), label (string, optional)
 */
const Toggle = ({ checked, onChange, label }) => {
  return (
    <label className={styles.toggleWrapper}>
      {label && <span className={styles.label}>{label}</span>}
      <div className={styles.toggle}>
        <input 
          type="checkbox" 
          checked={checked} 
          onChange={(e) => onChange(e.target.checked)} 
        />
        <span className={styles.slider} />
      </div>
    </label>
  );
};

export default Toggle;
