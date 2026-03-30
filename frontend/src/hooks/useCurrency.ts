import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import settingsService from '@/services/api/settings';
import {
  currencyDefaultLocale,
  DEFAULT_CURRENCY_CODE,
  DEFAULT_CURRENCY_LOCALE,
  formatCurrencyValue,
  formatPlainNumber,
  isCurrencyCode,
  normalizeCurrencyCode,
} from '@/lib/currency';

interface CurrencyConfig {
  currencyCode: string;
  currencySymbol: string;
  displayCurrency: string;
  useSymbolOnly: boolean;
  locale: string;
}

const readString = (source: Record<string, unknown>, keys: string[]): string => {
  for (const key of keys) {
    const value = source[key];
    if (value === undefined || value === null) continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return '';
};

const buildCurrencyConfig = (settings: Record<string, unknown>): CurrencyConfig => {
  const rawCurrency = readString(settings, ['default_currency', 'currency', 'site_currency']);
  const currencyCode = normalizeCurrencyCode(rawCurrency);
  const useSymbolOnly = Boolean(rawCurrency) && !isCurrencyCode(rawCurrency);
  const currencySymbol = useSymbolOnly ? rawCurrency : '';

  const localeFromSetting = readString(settings, ['currency_locale', 'locale']);
  const locale = localeFromSetting || currencyDefaultLocale(currencyCode) || DEFAULT_CURRENCY_LOCALE;

  return {
    currencyCode,
    currencySymbol,
    displayCurrency: currencySymbol || currencyCode,
    useSymbolOnly,
    locale,
  };
};

export const useCurrency = () => {
  const { data } = useQuery({
    queryKey: ['public-currency-settings'],
    queryFn: async () => {
      const response = await settingsService.getPublic();
      return (response?.data ?? {}) as Record<string, unknown>;
    },
    staleTime: 1000 * 60 * 5,
  });

  const config = useMemo(() => {
    if (!data || typeof data !== 'object') {
      return {
        currencyCode: DEFAULT_CURRENCY_CODE,
        currencySymbol: '',
        displayCurrency: DEFAULT_CURRENCY_CODE,
        useSymbolOnly: false,
        locale: DEFAULT_CURRENCY_LOCALE,
      };
    }
    return buildCurrencyConfig(data);
  }, [data]);

  const formatCurrency = (amount: number, options?: { minimumFractionDigits?: number; maximumFractionDigits?: number }) => {
    if (config.useSymbolOnly && config.currencySymbol) {
      const formatted = formatPlainNumber(amount, config.locale, {
        minimumFractionDigits: options?.minimumFractionDigits ?? 2,
        maximumFractionDigits: options?.maximumFractionDigits ?? 2,
      });
      return `${config.currencySymbol}${formatted}`;
    }
    return formatCurrencyValue(amount, config.currencyCode, config.locale, options);
  };

  const formatNumber = (amount: number, options?: { minimumFractionDigits?: number; maximumFractionDigits?: number }) =>
    formatPlainNumber(amount, config.locale, options);

  return {
    ...config,
    formatCurrency,
    formatNumber,
  };
};
