export const DEFAULT_CURRENCY_CODE = 'INR';
export const DEFAULT_CURRENCY_LOCALE = 'en-IN';

type CurrencyFormatOptions = {
  minimumFractionDigits?: number;
  maximumFractionDigits?: number;
};

export const normalizeCurrencyCode = (raw: unknown): string => {
  const code = String(raw ?? '').trim().toUpperCase();
  return /^[A-Z]{3}$/.test(code) ? code : DEFAULT_CURRENCY_CODE;
};

export const isCurrencyCode = (raw: unknown): boolean => {
  const code = String(raw ?? '').trim().toUpperCase();
  return /^[A-Z]{3}$/.test(code);
};

export const currencyDefaultLocale = (currencyCode: string): string => {
  if (currencyCode === 'INR') return 'en-IN';
  if (currencyCode === 'USD') return 'en-US';
  if (currencyCode === 'EUR') return 'en-IE';
  return DEFAULT_CURRENCY_LOCALE;
};

export const formatCurrencyValue = (
  amount: number,
  currencyCode: string,
  locale: string,
  options: CurrencyFormatOptions = {}
): string => {
  const value = Number.isFinite(amount) ? amount : 0;
  const { minimumFractionDigits = 2, maximumFractionDigits = 2 } = options;

  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits,
      maximumFractionDigits,
    }).format(value);
  } catch {
    return `${currencyCode} ${value.toFixed(Math.max(minimumFractionDigits, 0))}`;
  }
};

export const formatPlainNumber = (
  amount: number,
  locale: string,
  options: { minimumFractionDigits?: number; maximumFractionDigits?: number } = {}
): string => {
  const value = Number.isFinite(amount) ? amount : 0;
  const { minimumFractionDigits = 0, maximumFractionDigits = 0 } = options;

  try {
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits,
      maximumFractionDigits,
    }).format(value);
  } catch {
    return value.toFixed(Math.max(minimumFractionDigits, 0));
  }
};
