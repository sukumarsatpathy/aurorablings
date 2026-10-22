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
};

export default bulkReceiveService;
