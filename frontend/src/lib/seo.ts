export interface SeoPayload {
  title: string;
  description: string;
  image?: string;
  imageAlt?: string;
  url?: string;
  type?: string;
  siteName?: string;
}

const ensureMeta = (
  selector: string,
  create: () => HTMLMetaElement,
): HTMLMetaElement => {
  const existing = document.head.querySelector(selector);
  if (existing instanceof HTMLMetaElement) return existing;
  const meta = create();
  document.head.appendChild(meta);
  return meta;
};

const setMetaByName = (name: string, content: string) => {
  const meta = ensureMeta(`meta[name="${name}"]`, () => {
    const element = document.createElement('meta');
    element.setAttribute('name', name);
    return element;
  });
  meta.setAttribute('content', content);
};

const setMetaByProperty = (property: string, content: string) => {
  const meta = ensureMeta(`meta[property="${property}"]`, () => {
    const element = document.createElement('meta');
    element.setAttribute('property', property);
    return element;
  });
  meta.setAttribute('content', content);
};

const setCanonical = (href: string) => {
  const existing = document.head.querySelector('link[rel="canonical"]');
  const link = existing instanceof HTMLLinkElement ? existing : document.createElement('link');
  link.setAttribute('rel', 'canonical');
  link.setAttribute('href', href);
  if (!(existing instanceof HTMLLinkElement)) {
    document.head.appendChild(link);
  }
};

export const stripHtml = (value: string): string =>
  String(value || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

export const truncateText = (value: string, maxLength = 160): string => {
  const normalized = stripHtml(value);
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trim()}...`;
};

export const toAbsoluteUrl = (value?: string | null): string => {
  const normalized = String(value || '').trim();
  if (!normalized) return '';
  try {
    return new URL(normalized, window.location.origin).toString();
  } catch {
    return '';
  }
};

export const applySeo = ({
  title,
  description,
  image,
  imageAlt,
  url,
  type = 'website',
  siteName,
}: SeoPayload) => {
  const resolvedTitle = String(title || '').trim();
  const resolvedDescription = truncateText(description || '');
  const resolvedImage = toAbsoluteUrl(image);
  const resolvedUrl = toAbsoluteUrl(url || window.location.href);
  const resolvedImageAlt = String(imageAlt || resolvedTitle || siteName || '').trim();
  const twitterCard = resolvedImage ? 'summary_large_image' : 'summary';

  document.title = resolvedTitle;
  setMetaByName('description', resolvedDescription);

  setMetaByProperty('og:type', type);
  setMetaByProperty('og:title', resolvedTitle);
  setMetaByProperty('og:description', resolvedDescription);
  setMetaByProperty('og:url', resolvedUrl);

  if (siteName) {
    setMetaByProperty('og:site_name', siteName);
  }

  if (resolvedImage) {
    setMetaByProperty('og:image', resolvedImage);
    setMetaByProperty('og:image:secure_url', resolvedImage);
    if (resolvedImageAlt) {
      setMetaByProperty('og:image:alt', resolvedImageAlt);
    }
  }

  setMetaByName('twitter:card', twitterCard);
  setMetaByName('twitter:title', resolvedTitle);
  setMetaByName('twitter:description', resolvedDescription);

  if (resolvedImage) {
    setMetaByName('twitter:image', resolvedImage);
    if (resolvedImageAlt) {
      setMetaByName('twitter:image:alt', resolvedImageAlt);
    }
  }

  setCanonical(resolvedUrl);
};
