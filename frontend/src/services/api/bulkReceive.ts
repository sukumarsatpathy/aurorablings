import apiClient from './client';

export interface BulkReceiveOption {
  attribute: string;
  value: string;
  hex_code?: string;
}

export interface BulkReceiveVariant {
  id: string;
  sku: string;
  name: string;
  /** Number on the printed label. */
  barcode?: string | null;
  /** Short name the label prints (override or automatic). */
  label_text?: string;
  /** Regular price — what the label prints as MRP. */
  price?: string;
  is_active: boolean;
  /** Units physically in the chosen warehouse now. */
  on_hand: number;
  available: number;
  image: string | null;
  options: BulkReceiveOption[];
}

export interface BulkReceiveProduct {
  id: string;
  name: string;
  stock_id: number | null;
  is_active: boolean;
  category: string;
  /** Label roll this product prints on, from its category. */
  label_paper?: string;
  image: string | null;
  attributes: Array<{
    name: string;
    show_swatches?: boolean;
    values: Array<{ value: string; hex_code?: string }>;
  }>;
  variants: BulkReceiveVariant[];
}

export interface BulkReceiveWarehouse {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
  is_default: boolean;
}

export interface BulkReceiveResult {
  total_quantity: number;
  variants: number;
  products: number;
  lines: Array<{ variant_id: string; sku: string; quantity: number; on_hand_after: number }>;
}

const rowsOf = <T,>(payload: unknown): T[] => {
  const p = payload as { data?: unknown; results?: unknown };
  if (Array.isArray(p?.data)) return p.data as T[];
  const nested = (p?.data as { results?: unknown })?.results;
  if (Array.isArray(nested)) return nested as T[];
  if (Array.isArray(p?.results)) return p.results as T[];
  if (Array.isArray(payload)) return payload as T[];
  return [];
};

const bulkReceiveService = {
  listWarehouses: async (): Promise<BulkReceiveWarehouse[]> => {
    const response = await apiClient.get('/v1/inventory/warehouses/');
    return rowsOf<BulkReceiveWarehouse>(response.data);
  },

  /** Every non-deleted product with variants, options and stock in `warehouseId`. */
  catalog: async (warehouseId: string): Promise<BulkReceiveProduct[]> => {
    const response = await apiClient.get('/v1/inventory/stock/bulk-receive/catalog/', {
      params: { warehouse_id: warehouseId || undefined },
    });
    return rowsOf<BulkReceiveProduct>(response.data);
  },

  receive: async (payload: {
    warehouse_id: string;
    reference_id?: string;
    notes?: string;
    items: Array<{ variant_id: string; quantity: number }>;
  }): Promise<{ data: BulkReceiveResult; message?: string }> => {
    const response = await apiClient.post('/v1/inventory/stock/bulk-receive/', payload);
    return response.data;
  },

  /**
   * Download a label sheet for the label printer app: one row per sticker
   * (Barcode, Name, SKU, MRP). One file is one label paper (roll): items whose
   * categories use different papers must be downloaded separately. Printing
   * never changes stock.
   */
  downloadLabels: async (
    items: Array<{ variant_id: string; copies: number }>,
    format: 'xlsx' | 'csv' = 'xlsx',
    paper?: string,
  ): Promise<number> => {
    const response = await apiClient.post(
      '/v1/inventory/labels/',
      { items, format, ...(paper ? { paper } : {}) },
      { responseType: 'blob' },
    );
    const disposition = String(response.headers['content-disposition'] || '');
    const name = disposition.match(/filename="([^"]+)"/)?.[1] || `labels.${format}`;
    const url = URL.createObjectURL(response.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    return Number(response.headers['x-label-count'] || 0);
  },
};

/** The server's message out of a blob error response (label download). */
export async function labelErrorMessage(error: unknown): Promise<string> {
  const data = (error as { response?: { data?: unknown } })?.response?.data;
  try {
    if (data instanceof Blob) {
      const parsed = JSON.parse(await data.text());
      return parsed?.message || parsed?.detail || 'Could not make the label file.';
    }
  } catch {
    /* fall through */
  }
  return 'Could not make the label file. Check your connection and try again.';
}

export default bulkReceiveService;
