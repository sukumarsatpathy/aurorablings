import React from 'react';
import OptimizedImage from '@/components/ui/OptimizedImage';

/**
 * Props: src (string|null), alt (string), bgColor (string), className (optional)
 * If src is null/empty, renders a <div> with bgColor background instead of <img>
 */
const ImageWithFallback = ({ src, alt, bgColor, className = '' }) => {
  if (!src) {
    return (
      <div 
        className={className} 
        style={{ 
          backgroundColor: bgColor || '#f5f0eb',
          width: '100%',
          height: '100%'
        }} 
      />
    );
  }

  return (
    <OptimizedImage
      src={src} 
      alt={alt} 
      className={className} 
      loading="lazy"
      decoding="async"
      width={1200}
      height={700}
      style={{ 
        width: '100%',
        height: '100%',
        objectFit: 'cover'
      }} 
      onError={(e) => {
        e.target.style.display = 'none';
        e.target.parentElement.style.backgroundColor = bgColor || '#f5f0eb';
      }}
    />
  );
};

export default ImageWithFallback;
