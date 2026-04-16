import React, { useMemo, useState } from 'react';

type LoadingMode = 'lazy' | 'eager';
type DecodingMode = 'async' | 'sync' | 'auto';

interface OptimizedImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'loading' | 'decoding'> {
  src: string;
  srcSet?: string;
  sizes?: string;
  priority?: boolean;
  loading?: LoadingMode;
  decoding?: DecodingMode;
  fallbackSrc?: string;
}

export const OptimizedImage: React.FC<OptimizedImageProps> = ({
  src,
  srcSet,
  sizes,
  priority = false,
  loading,
  decoding,
  fallbackSrc,
  width,
  height,
  style,
  onError,
  ...rest
}) => {
  const [errored, setErrored] = useState(false);

  const resolvedLoading: LoadingMode = loading || (priority ? 'eager' : 'lazy');
  const resolvedDecoding: DecodingMode = decoding || (priority ? 'sync' : 'async');
  const resolvedSrc = errored && fallbackSrc ? fallbackSrc : src;
  const resolvedSrcSet = errored ? undefined : srcSet;

  const mergedStyle = useMemo<React.CSSProperties>(
    () => ({
      ...(style || {}),
    }),
    [style]
  );

  return (
    <img
      {...rest}
      src={resolvedSrc}
      srcSet={resolvedSrcSet}
      sizes={sizes}
      width={width}
      height={height}
      loading={resolvedLoading}
      decoding={resolvedDecoding}
      fetchPriority={priority ? 'high' : 'auto'}
      style={mergedStyle}
      onError={(event) => {
        setErrored(true);
        onError?.(event);
      }}
    />
  );
};

export default OptimizedImage;

