import apiClient from './client';
import type {
  AdjustStockPayload,
  ReceiveStockPayload,
  TransferStockPayload,
  WarehouseWriteData,
} from '@/types/inventory';

const inventoryService = {
  listStock: async (params?: { search?: string; warehouse_id?: string; status?: 'in' | 'low' | 'out' | '' }) => {
    const response = await apiClient.get('/v1/inventory/stock/', { params });
    return response.data;
  },

  updateStockThreshold: async (id: string, low_stock_threshold: number) => {
    const response = await apiClient.patch(`/v1/inventory/stock/${id}/`, { low_stock_threshold });
    return response.data;
  },

  listVariants: async (params?: { search?: string; active_only?: boolean }) => {
    const response = await apiClient.get('/v1/inventory/stock/variants/', { params });
    return response.data;
  },

  listWarehouses: async (params?: { include_inactive?: boolean }) => {
    const response = await apiClient.get('/v1/inventory/warehouses/', { params });
    return response.data;
  },

  createWarehouse: async (data: WarehouseWriteData) => {
    const response = await apiClient.post('/v1/inventory/warehouses/', data);
    return response.data;
  },

  updateWarehouse: async (id: string, data: Partial<WarehouseWriteData>) => {
    const response = await apiClient.patch(`/v1/inventory/warehouses/${id}/`, data);
    return response.data;
  },

  deleteWarehouse: async (id: string) => {
    const response = await apiClient.delete(`/v1/inventory/warehouses/${id}/`);
    return response.data;
  },

  receiveStock: async (data: ReceiveStockPayload) => {
    const response = await apiClient.post('/v1/inventory/stock/receive/', data);
    return response.data;
  },

  adjustStock: async (data: AdjustStockPayload) => {
    const response = await apiClient.post('/v1/inventory/stock/adjust/', data);
    return response.data;
  },

  transferStock: async (data: TransferStockPayload) => {
    const response = await apiClient.post('/v1/inventory/stock/transfer/', data);
    return response.data;
  },
};

export default inventoryService;
