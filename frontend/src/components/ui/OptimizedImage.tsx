import React, { useMemo, useState } from 'react';

type LoadingMode = 'lazy' | 'eager';
type DecodingMode = 'async' | 'sync' | 'auto';

/** A typed <source> for the <picture> wrapper, e.g. image/avif ahead of the WebP img. */
export interface PictureSource {
  type: string;
  srcSet: string;
}

interface OptimizedImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'loading' | 'decoding'> {
  src: string;
  srcSet?: string;
  sizes?: string;
  priority?: boolean;
  loading?: LoadingMode;
  decoding?: DecodingMode;
  fallbackSrc?: string;
  /**
   * Opt-in. When non-empty the img is wrapped in a <picture> and these are
   * emitted as <source> elements ahead of it, in order. The browser takes the
   * first type it can decode and ignores the rest, so the img stays the
   * universal fallback and nothing breaks on older engines.
   *
   * Dropped entirely once the img has errored, so the fallbackSrc path is not
   * shadowed by a <source> that would win over it.
   */
  sources?: PictureSource[];
}

export const OptimizedImage: React.FC<OptimizedImageProps> = ({
  src,
  srcSet,
  sizes,
  priority = false,
  loading,
  decoding,
  fallbackSrc,
  sources,
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

  const img = (
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

  const activeSources = errored ? [] : (sources || []).filter((s) => s.type && s.srcSet);
  if (!activeSources.length) return img;

  // <picture> is inline by default. The img inside typically carries
  // height: 100%, which would then resolve against a shrink-to-fit inline box
  // and collapse. Forcing block/100% makes the wrapper layout-neutral, so
  // adding sources cannot change how any existing caller renders.
  return (
    <picture style={{ display: 'block', width: '100%', height: '100%' }}>
      {activeSources.map((source) => (
        <source key={source.type} type={source.type} srcSet={source.srcSet} sizes={sizes} />
      ))}
      {img}
    </picture>
  );
};

export default OptimizedImage;

