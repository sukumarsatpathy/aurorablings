export const extractData = <T = any>(payload: any): T | null => {
  if (payload?.data && typeof payload.data === 'object' && !Array.isArray(payload.data)) {
    return payload.data as T;
  }
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    return payload as T;
  }
  return null;
};

export const extractRows = <T = any>(payload: any): T[] => {
  if (Array.isArray(payload?.data)) return payload.data as T[];
  if (Array.isArray(payload?.data?.results)) return payload.data.results as T[];
  if (Array.isArray(payload?.results)) return payload.results as T[];
  if (Array.isArray(payload)) return payload as T[];
  return [];
};

export const formatStatus = (value?: string | null): string => {
  if (!value) return 'N/A';
  return String(value)
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const formatDateTime = (value?: string | null): string => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'N/A';
  return parsed.toLocaleString();
};

