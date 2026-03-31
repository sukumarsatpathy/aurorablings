import apiClient from './client';

export interface CatalogCategory {
  id: string;
  name: string;
}

export interface CatalogMedia {
  id: string;
  image: string;
  alt_text: string;
  is_primary: boolean;
  sort_order: number;
}

export interface CatalogVariant {
  id: string;
  sku: string;
  name: string;
  price: string;
  compare_at_price?: string | null;
  effective_price?: string;
  display_compare_at_price?: string | null;
  stock_quantity: number;
  is_default: boolean;
  has_active_offer?: boolean;
  offer_price?: string | null;
  offer_starts_at?: string | null;
  offer_ends_at?: string | null;
  offer_label?: string;
  offer_is_active?: boolean;
  discount_percentage?: number | null;
  is_in_stock?: boolean;
  is_low_stock?: boolean;
  attribute_values?: Array<{ attribute_name: string; value: string }>;
}

export interface CatalogAttributeValue {
  id: string;
  value: string;
  sort_order: number;
}

export interface CatalogAttribute {
  id: string;
  name: string;
  sort_order: number;
  values: CatalogAttributeValue[];
}

export interface CatalogAdminAttribute {
  id: string;
  name: string;
  sort_order: number;
  is_active: boolean;
  linked_products: number;
  options: string[];
}

export interface CatalogProductDetail {
  id: string;
  name: string;
  slug: string;
  description: string;
  short_description: string;
  is_active: boolean;
  rating?: string | number;
  avg_rating?: string | number;
  review_count?: number;
  category: { id: string; name: string; slug?: string };
  media: CatalogMedia[];
  variants: CatalogVariant[];
  attributes?: CatalogAttribute[];
  info_items?: Array<{
    id: string;
    title: string;
    value: string;
    sort_order: number;
    is_active: boolean;
  }>;
}

export interface CatalogProductInfoItem {
  id: string;
  title: string;
  value: string;
  sort_order: number;
  is_active: boolean;
}

export interface ProductNotifyPayload {
  variant_id?: string;
  name?: string;
  email?: string;
  phone?: string;
  quantity?: number;
  notes?: string;
}

const catalogService = {
  listProducts: async (params?: Record<string, unknown>) => {
    const response = await apiClient.get('/v1/catalog/products/', { params });
    return response.data;
  },

  listAllProducts: async () => {
    const pageSize = 100;
    const first = await apiClient.get('/v1/catalog/products/', {
      params: { page: 1, page_size: pageSize },
    });
    const firstPayload = first.data;

    const extractRows = (payload: any): any[] => {
      if (Array.isArray(payload?.data)) return payload.data;
      if (Array.isArray(payload?.data?.results)) return payload.data.results;
      if (Array.isArray(payload?.results)) return payload.results;
      if (Array.isArray(payload)) return payload;
      return [];
    };

    const extractCount = (payload: any): number => {
      const root = payload?.data && typeof payload.data === 'object' ? payload.data : payload;
      const meta = payload?.meta && typeof payload.meta === 'object' ? payload.meta : root?.meta;
      const count = Number(
        meta?.total_count ??
        root?.total_count ??
        root?.count ??
        root?.total ??
        0
      );
      return Number.isFinite(count) ? count : 0;
    };

    const allRows = [...extractRows(firstPayload)];
    const count = extractCount(firstPayload);
    if (!count || allRows.length >= count) return allRows;

    const totalPages = Math.ceil(count / pageSize);
    for (let page = 2; page <= totalPages; page += 1) {
      const response = await apiClient.get('/v1/catalog/products/', {
        params: { page, page_size: pageSize },
      });
      allRows.push(...extractRows(response.data));
    }

    return allRows;
  },

  listDeals: async () => {
    const response = await apiClient.get('/v1/catalog/products/deals/');
    return response.data;
  },

  getProduct: async (id: string) => {
    const response = await apiClient.get(`/v1/catalog/products/${id}/`);
    return response.data;
  },

  getProductBySlug: async (slug: string) => {
    const response = await apiClient.get(`/v1/catalog/products/slug/${slug}/`);
    return response.data;
  },

  listCategories: async () => {
    const response = await apiClient.get('/v1/catalog/categories/');
    return response.data;
  },

  createCategory: async (payload: FormData | { name: string; is_active?: boolean }) => {
    const response = await apiClient.post('/v1/catalog/categories/', payload, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  updateCategory: async (id: string, payload: FormData | { name?: string; is_active?: boolean; description?: string }) => {
    const response = await apiClient.patch(`/v1/catalog/categories/${id}/`, payload, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deleteCategory: async (id: string) => {
    const response = await apiClient.delete(`/v1/catalog/categories/${id}/`);
    return response.data;
  },

  createProduct: async (payload: {
    name: string;
    category_id: string;
    description?: string;
    short_description?: string;
    is_active?: boolean;
  }) => {
    const response = await apiClient.post('/v1/catalog/products/', payload);
    return response.data;
  },

  updateProduct: async (id: string, payload: Partial<{
    name: string;
    category_id: string;
    description: string;
    short_description: string;
    is_active: boolean;
  }>) => {
    const response = await apiClient.patch(`/v1/catalog/products/${id}/`, payload);
    return response.data;
  },

  deleteProduct: async (id: string) => {
    const response = await apiClient.delete(`/v1/catalog/products/${id}/`);
    return response.data;
  },

  listProductInfoItems: async (productId: string) => {
    const response = await apiClient.get(`/v1/catalog/products/${productId}/info-items/`);
    return response.data;
  },

  createProductInfoItem: async (
    productId: string,
    payload: { title: string; value: string; sort_order?: number; is_active?: boolean }
  ) => {
    const response = await apiClient.post(`/v1/catalog/products/${productId}/info-items/`, payload);
    return response.data;
  },

  updateProductInfoItem: async (
    productId: string,
    itemId: string,
    payload: Partial<{ title: string; value: string; sort_order: number; is_active: boolean }>
  ) => {
    const response = await apiClient.patch(`/v1/catalog/products/${productId}/info-items/${itemId}/`, payload);
    return response.data;
  },

  deleteProductInfoItem: async (productId: string, itemId: string) => {
    const response = await apiClient.delete(`/v1/catalog/products/${productId}/info-items/${itemId}/`);
    return response.data;
  },

  reorderProductInfoItems: async (
    productId: string,
    items: Array<{ id: string; sort_order: number }>
  ) => {
    const response = await apiClient.post(`/v1/catalog/products/${productId}/info-items/reorder/`, { items });
    return response.data;
  },

  listProductAttributes: async (productId: string) => {
    const response = await apiClient.get(`/v1/catalog/products/${productId}/attributes/`);
    return response.data;
  },

  createProductAttribute: async (productId: string, payload: { global_attribute_id?: string; name?: string; options?: string[] }) => {
    const response = await apiClient.post(`/v1/catalog/products/${productId}/attributes/`, payload);
    return response.data;
  },

  updateProductAttribute: async (productId: string, attributeId: string, payload: Partial<{ name: string; options: string[] }>) => {
    const response = await apiClient.patch(`/v1/catalog/products/${productId}/attributes/${attributeId}/`, payload);
    return response.data;
  },

  deleteProductAttribute: async (productId: string, attributeId: string) => {
    const response = await apiClient.delete(`/v1/catalog/products/${productId}/attributes/${attributeId}/`);
    return response.data;
  },

  listAttributes: async (params?: { search?: string }) => {
    const response = await apiClient.get('/v1/catalog/attributes/', { params });
    return response.data;
  },

  createAttribute: async (payload: { name: string; options?: string[]; sort_order?: number; is_active?: boolean }) => {
    const response = await apiClient.post('/v1/catalog/attributes/', payload);
    return response.data;
  },

  updateAttribute: async (id: string, payload: Partial<{ name: string; options: string[]; sort_order: number; is_active: boolean }>) => {
    const response = await apiClient.patch(`/v1/catalog/attributes/${id}/`, payload);
    return response.data;
  },

  deleteAttribute: async (id: string) => {
    const response = await apiClient.delete(`/v1/catalog/attributes/${id}/`);
    return response.data;
  },

  createVariant: async (productId: string, payload: {
    sku: string;
    price: number;
    stock_quantity?: number;
    is_default?: boolean;
    name?: string;
    attribute_value_ids?: string[];
    offer_price?: number | null;
    offer_starts_at?: string | null;
    offer_ends_at?: string | null;
    offer_label?: string;
    offer_is_active?: boolean;
  }) => {
    const response = await apiClient.post(`/v1/catalog/products/${productId}/variants/`, payload);
    return response.data;
  },

  updateVariant: async (variantId: string, payload: Partial<{
    sku: string;
    price: number;
    stock_quantity: number;
    is_default: boolean;
    name: string;
    attribute_value_ids: string[];
    offer_price: number | null;
    offer_starts_at: string | null;
    offer_ends_at: string | null;
    offer_label: string;
    offer_is_active: boolean;
  }>) => {
    const response = await apiClient.patch(`/v1/catalog/variants/${variantId}/`, payload);
    return response.data;
  },

  deleteVariant: async (variantId: string) => {
    const response = await apiClient.delete(`/v1/catalog/variants/${variantId}/`);
    return response.data;
  },

  uploadProductMedia: async (
    productId: string,
    file: File,
    data?: { alt_text?: string; is_primary?: boolean; sort_order?: number }
  ) => {
    const form = new FormData();
    form.append('image', file);
    if (data?.alt_text) form.append('alt_text', data.alt_text);
    if (typeof data?.is_primary === 'boolean') form.append('is_primary', data.is_primary ? 'true' : 'false');
    if (typeof data?.sort_order === 'number') form.append('sort_order', String(data.sort_order));

    const response = await apiClient.post(`/v1/catalog/products/${productId}/media/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  updateProductMedia: async (
    productId: string,
    mediaId: string,
    payload: Partial<{ alt_text: string; is_primary: boolean; sort_order: number }>
  ) => {
    const response = await apiClient.patch(`/v1/catalog/products/${productId}/media/${mediaId}/`, payload);
    return response.data;
  },

  deleteProductMedia: async (productId: string, mediaId: string) => {
    const response = await apiClient.delete(`/v1/catalog/products/${productId}/media/${mediaId}/`);
    return response.data;
  },

  notifyMe: async (productId: string, payload: ProductNotifyPayload) => {
    const response = await apiClient.post(`/v1/catalog/products/${productId}/notify-me/`, payload);
    return response.data;
  },
};

export default catalogService;
