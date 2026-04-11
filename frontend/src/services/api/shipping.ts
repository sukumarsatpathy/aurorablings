import apiClient from './client';

const shippingService = {
  listShipments: async (params?: { status?: string; provider?: string }) => {
    const response = await apiClient.get('/v1/logistics/shipments/', { params });
    return response.data;
  },

  getOrderShipment: async (orderId: string) => {
    const response = await apiClient.get(`/v1/logistics/orders/${orderId}/shipment/`);
    return response.data;
  },

  getMyOrderShippingStatus: async (orderId: string) => {
    const response = await apiClient.get(`/v1/logistics/orders/${orderId}/shipping-status/`);
    return response.data;
  },

  approveOrderShipping: async (
    orderId: string,
    payload: {
      fulfillment_method: 'local_delivery' | 'nimbuspost' | 'shiprocket';
      notes?: string;
      rider_name?: string;
      rider_phone?: string;
      local_notes?: string;
      local_expected_delivery_date?: string | null;
    }
  ) => {
    const response = await apiClient.post(`/v1/logistics/orders/${orderId}/shipping/approve/`, payload);
    return response.data;
  },

  createShipmentForOrder: async (orderId: string, force = false) => {
    const response = await apiClient.post(`/v1/logistics/orders/${orderId}/shipment/create/`, { force });
    return response.data;
  },

  preflightOrderShipment: async (orderId: string) => {
    const response = await apiClient.get(`/v1/logistics/orders/${orderId}/shipment/preflight/`);
    return response.data;
  },

  requestPickup: async (shipmentId: string) => {
    const response = await apiClient.post(`/v1/logistics/shipments/${shipmentId}/pickup/`);
    return response.data;
  },

  refreshTracking: async (shipmentId: string) => {
    const response = await apiClient.post(`/v1/logistics/shipments/${shipmentId}/refresh-tracking/`);
    return response.data;
  },

  cancelShipment: async (shipmentId: string) => {
    const response = await apiClient.post(`/v1/logistics/shipments/${shipmentId}/cancel/`);
    return response.data;
  },

  updateLocalDeliveryStatus: async (
    shipmentId: string,
    payload: {
      local_delivery_status: 'assigned' | 'out_for_delivery' | 'delivered' | 'cancelled';
      rider_name?: string;
      rider_phone?: string;
      local_notes?: string;
      local_expected_delivery_date?: string | null;
    }
  ) => {
    const response = await apiClient.post(`/v1/logistics/shipments/${shipmentId}/local-status/`, payload);
    return response.data;
  },
};

export default shippingService;
