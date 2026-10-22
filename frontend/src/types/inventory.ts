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
  category_name?: string;
  product_image?: string | null;
  is_active: boolean;
}

export interface DeletedStockRecordSummary {
  id: string;
  sku: string;
  warehouse_code: string;
  product: string;
  on_hand: number;
  reserved: number;
  available: number;
  low_stock_threshold: number;
  ledger_entries_deleted: number;
  reservations_deleted: number;
}

export interface BlockedStockRecordSummary {
  id: string;
  sku: string;
  warehouse_code: string;
  reserved: number;
  active_reservations: number;
  reason: string;
}

export interface BulkDeleteStockResult {
  deleted: number;
  deleted_records: DeletedStockRecordSummary[];
  blocked: BlockedStockRecordSummary[];
  missing: string[];
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
