export type WarehouseType = 'warehouse' | 'store' | 'virtual';

export interface Warehouse {
  id: string;
  name: string;
  code: string;
  type: WarehouseType;
  address: string;
  is_active: boolean;
  is_default: boolean;
}

export interface InventoryStockRecord {
  id: string;
  variant_id: string;
  warehouse_id: string;
  sku: string;
  variant_name: string;
  product_name: string;
  warehouse_name: string;
  warehouse_code: string;
  on_hand: number;
  reserved: number;
  available: number;
  low_stock_threshold: number;
  is_in_stock: boolean;
  is_low_stock: boolean;
  updated_at: string;
}

export interface InventoryVariantOption {
  id: string;
  sku: string;
  name: string;
  product_name: string;
  is_active: boolean;
}

export interface WarehouseWriteData {
  name: string;
  code: string;
  type: WarehouseType;
  address?: string;
  is_active?: boolean;
  is_default?: boolean;
}

export interface ReceiveStockPayload {
  variant_id: string;
  warehouse_id: string;
  quantity: number;
  reference_id?: string;
  notes?: string;
}

export interface AdjustStockPayload {
  variant_id: string;
  warehouse_id: string;
  quantity_delta: number;
  reason: string;
}

export interface TransferStockPayload {
  variant_id: string;
  from_warehouse_id: string;
  to_warehouse_id: string;
  quantity: number;
  notes?: string;
}
