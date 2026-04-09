import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Plus, Search, MoreHorizontal, Edit, Trash2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalFooter,
} from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import catalogService, { type CatalogProductDetail } from '@/services/api/catalog';
import { useCurrency } from '@/hooks/useCurrency';
import { LexicalHtmlEditor } from '@/components/admin/LexicalHtmlEditor';
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';

interface ProductAttribute {
  id?: string;
  globalAttributeId?: string;
  name: string;
  options: string[];
  persisted?: boolean;
}

interface ProductVariation {
  id: string;
  sku: string;
  attributes: Record<string, string>;
  price: number;
  offerPrice?: number | null;
  offerStartsAt?: string;
  offerEndsAt?: string;
  offerLabel?: string;
  offerIsActive?: boolean;
  persisted?: boolean;
}

interface ProductMedia {
  id: string;
  url: string;
  altText: string;
  isPrimary: boolean;
  sortOrder: number;
  file?: File;
  persisted?: boolean;
}

interface ProductInfoItemRow {
  id: string;
  title: string;
  value: string;
  sortOrder: number;
  isActive: boolean;
  persisted?: boolean;
}

interface Product {
  id: string;
  name: string;
  description: string;
  category: string;
  categoryId: string;
  basePrice: number;
  imageCount?: number;
  variantCount?: number;
  hasActiveOffer: boolean;
  status: string;
  attributes: ProductAttribute[];
  infoItems: ProductInfoItemRow[];
  variations: ProductVariation[];
  media: ProductMedia[];
}

interface ProductFormData {
  name: string;
  description: string;
  category: string;
  categoryId: string;
  basePrice: number;
  status: string;
  attributes: ProductAttribute[];
  infoItems: ProductInfoItemRow[];
  variations: ProductVariation[];
  media: ProductMedia[];
}

interface CategoryOption {
  id: string;
  name: string;
}

type VariationFieldErrors = {
  sku?: string;
  price?: string;
  offer?: string;
};

type ProductFormErrors = {
  name?: string;
  categoryId?: string;
  basePrice?: string;
  variations?: string;
  categoryName?: string;
  variationById?: Record<string, VariationFieldErrors>;
};

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

const extractRows = (payload: any): any[] => {
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.data?.results)) return payload.data.results;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload)) return payload;
  return [];
};

const pad2 = (value: number): string => String(value).padStart(2, '0');

const toLocalDateInput = (iso?: string): string => {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
};

const toLocalTimeInput = (iso?: string): string => {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
};

const localDateTimeToIso = (localDate: string, localTime: string): string => {
  if (!localDate) return '';
  const safeTime = localTime || '00:00';
  const composed = new Date(`${localDate}T${safeTime}:00`);
  if (Number.isNaN(composed.getTime())) return '';
  return composed.toISOString();
};

const normalizeKey = (value: string): string => value.trim().toLowerCase();

const buildAttributeValueIdMap = (detail: CatalogProductDetail): Record<string, string> => {
  const result: Record<string, string> = {};
  for (const attr of detail.attributes || []) {
    const attrKey = normalizeKey(attr.name || '');
    for (const val of attr.values || []) {
      const valueKey = normalizeKey(val.value || '');
      if (!attrKey || !valueKey) continue;
      result[`${attrKey}::${valueKey}`] = val.id;
    }
  }
  return result;
};

const getBackendOrigin = (): string => {
  const baseURL = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const explicitBackendOrigin = import.meta.env.VITE_BACKEND_ORIGIN as string | undefined;

  if (explicitBackendOrigin) {
    try {
      return new URL(explicitBackendOrigin).origin;
    } catch {
      // ignore invalid env and continue fallback
    }
  }

  try {
    if (baseURL) {
      const parsed = new URL(baseURL, window.location.origin);
      if (/^https?:$/i.test(parsed.protocol) && parsed.origin !== window.location.origin) {
        return parsed.origin;
      }
    }
  } catch {
    // ignore and fallback
  }

  // Local docker/dev fallback when API base is relative (e.g. /api)
  if (['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }

  return window.location.origin;
};

const normalizeAssetUrl = (raw?: string | null): string => {
  const value = String(raw || '').trim();
  if (!value) return '';

  const backendOrigin = getBackendOrigin();

  // Relative asset path from API
  if (value.startsWith('/')) {
    return `${backendOrigin}${value}`;
  }

  try {
    const parsed = new URL(value);
    // Docker internal hostnames are not browser-reachable outside containers.
    if (['backend', 'backend-1', 'web', 'api'].includes(parsed.hostname)) {
      parsed.protocol = window.location.protocol;
      parsed.hostname = window.location.hostname;
      if (!parsed.port) {
        parsed.port = '8000';
      }
      return parsed.toString();
    }
    return value;
  } catch {
    return value;
  }
};

const mapDetailToProduct = (raw: CatalogProductDetail): Product => ({
  id: raw.id,
  name: raw.name || '',
  description: raw.description || '',
  category: raw.category?.name || '',
  categoryId: raw.category?.id || '',
  basePrice: raw.variants?.[0]?.price ? Number(raw.variants[0].price) : 0,
  variantCount: (raw.variants || []).length,
  hasActiveOffer: (raw.variants || []).some(v => (v as any).has_active_offer),
  status: raw.is_active ? 'Active' : 'Draft',
  attributes: (raw.attributes || []).map((attr) => ({
    id: attr.id,
    name: attr.name,
    options: (attr.values || []).map((v) => v.value),
    persisted: true,
  })),
  infoItems: (raw.info_items || []).map((item) => ({
    id: item.id,
    title: item.title || '',
    value: item.value || '',
    sortOrder: Number(item.sort_order || 0),
    isActive: Boolean(item.is_active),
    persisted: true,
  })),
  variations: (raw.variants || []).map((v) => ({
    id: v.id,
    sku: v.sku,
    attributes: Object.fromEntries((v.attribute_values || []).map((a) => [a.attribute_name, a.value])),
    price: Number(v.price),
    offerPrice: (v as any).offer_price ? Number((v as any).offer_price) : null,
    offerStartsAt: (v as any).offer_starts_at || '',
    offerEndsAt: (v as any).offer_ends_at || '',
    offerLabel: (v as any).offer_label || '',
    offerIsActive: Boolean((v as any).offer_is_active),
    persisted: true,
  })),
  media: (raw.media || []).map((m) => ({
    id: m.id,
    url: normalizeAssetUrl(m.image),
    altText: m.alt_text || '',
    isPrimary: !!m.is_primary,
    sortOrder: Number(m.sort_order || 0),
    persisted: true,
  })),
});

const SortableInfoItemRow: React.FC<{
  item: ProductInfoItemRow;
  onUpdate: (id: string, patch: Partial<ProductInfoItemRow>) => void;
  onDelete: (id: string) => void;
}> = ({ item, onUpdate, onDelete }) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: item.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} className="rounded-lg border border-border/70 bg-white p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <button type="button" className="h-8 w-8 inline-flex items-center justify-center rounded border border-border text-muted-foreground cursor-grab active:cursor-grabbing" {...attributes} {...listeners}>
          <GripVertical size={14} />
        </button>
        <button type="button" className="text-xs text-destructive font-medium" onClick={() => onDelete(item.id)}>
          Remove
        </button>
      </div>
      <Input
        value={item.title}
        onChange={(e) => onUpdate(item.id, { title: e.target.value })}
        placeholder="Title (e.g. Weight)"
        className="h-9"
      />
      <Input
        value={item.value}
        onChange={(e) => onUpdate(item.id, { value: e.target.value })}
        placeholder="Value (e.g. 500 g)"
        className="h-9"
      />
    </div>
  );
};

export const ProductManagement: React.FC = () => {
  const navigate = useNavigate();
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [globalAttributes, setGlobalAttributes] = useState<Array<{ id: string; name: string; options: string[] }>>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [offerFilter, setOfferFilter] = useState<'all' | 'active' | 'none'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(20);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [originalVariantIds, setOriginalVariantIds] = useState<string[]>([]);
  const [originalMediaIds, setOriginalMediaIds] = useState<string[]>([]);
  const [originalAttributeIds, setOriginalAttributeIds] = useState<string[]>([]);
  const [originalInfoItemIds, setOriginalInfoItemIds] = useState<string[]>([]);

  const [formData, setFormData] = useState<ProductFormData>({
    name: '',
    description: '',
    category: '',
    categoryId: '',
    basePrice: 0,
    status: 'Active',
    attributes: [],
    infoItems: [],
    variations: [],
    media: [],
  });

  const [isCreatingAttr, setIsCreatingAttr] = useState(false);
  const [newAttrData, setNewAttrData] = useState({ name: '', options: '' });
  const [isDragOverUploader, setIsDragOverUploader] = useState(false);
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [isSavingCategory, setIsSavingCategory] = useState(false);
  const [categorySearch, setCategorySearch] = useState('');
  const [isCategoryDropdownOpen, setIsCategoryDropdownOpen] = useState(false);
  const [productToDelete, setProductToDelete] = useState<string | null>(null);
  const [isDeletingProduct, setIsDeletingProduct] = useState(false);
  const [deleteProductError, setDeleteProductError] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<ProductFormErrors>({});
  const mediaInputRef = useRef<HTMLInputElement | null>(null);
  const nameFieldRef = useRef<HTMLDivElement | null>(null);
  const categoryFieldRef = useRef<HTMLDivElement | null>(null);
  const categoryDropdownRef = useRef<HTMLDivElement | null>(null);
  const basePriceFieldRef = useRef<HTMLDivElement | null>(null);
  const variationsSectionRef = useRef<HTMLDivElement | null>(null);
  const variationRowRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const flashTimeoutRef = useRef<number | null>(null);
  const { formatCurrency, displayCurrency } = useCurrency();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const clearError = (field: keyof ProductFormErrors) => {
    setFormErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const clearVariationError = (variationId: string, field: keyof VariationFieldErrors) => {
    setFormErrors((prev) => {
      const variationById = { ...(prev.variationById || {}) };
      const current = { ...(variationById[variationId] || {}) };
      delete current[field];
      if (Object.keys(current).length === 0) {
        delete variationById[variationId];
      } else {
        variationById[variationId] = current;
      }
      return { ...prev, variationById };
    });
  };

  const scrollAndFlashError = (el: HTMLElement | null) => {
    if (!el) return;

    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('ring-2', 'ring-destructive/50', 'rounded-lg');

    if (flashTimeoutRef.current) {
      window.clearTimeout(flashTimeoutRef.current);
    }
    flashTimeoutRef.current = window.setTimeout(() => {
      el.classList.remove('ring-2', 'ring-destructive/50', 'rounded-lg');
      flashTimeoutRef.current = null;
    }, 1200);
  };

  const focusFirstError = (errors: ProductFormErrors) => {
    if (errors.name) {
      scrollAndFlashError(nameFieldRef.current);
      return;
    }

    if (errors.categoryId) {
      scrollAndFlashError(categoryFieldRef.current);
      return;
    }

    if (errors.basePrice) {
      scrollAndFlashError(basePriceFieldRef.current);
      return;
    }

    if (errors.variationById) {
      const firstVariationWithError = formData.variations.find((v) => Boolean(errors.variationById?.[v.id]));
      if (firstVariationWithError) {
        scrollAndFlashError(variationRowRefs.current[firstVariationWithError.id]);
        return;
      }
    }

    if (errors.variations) {
      scrollAndFlashError(variationsSectionRef.current);
    }
  };

  const loadCatalog = async () => {
    try {
      setLoading(true);
      const [productsRes, categoriesRes, attributesRes] = await Promise.allSettled([
        catalogService.listAllProducts(),
        catalogService.listCategories(),
        catalogService.listAttributes(),
      ]);

      const productRows = productsRes.status === 'fulfilled' ? extractRows(productsRes.value) : [];
      const categoryRows = categoriesRes.status === 'fulfilled' ? extractRows(categoriesRes.value) : [];
      const globalAttributeRows = attributesRes.status === 'fulfilled' ? extractRows(attributesRes.value) : [];

      const categoryMap = new Map<string, string>(
        categoryRows.map((c: any) => [String(c.id), String(c.name || '')])
      );

      const mappedProducts: Product[] = productRows.map((p: any) => ({
        id: String(p.id),
        name: String(p.name || ''),
        description: '',
        category: String(p.category_name || ''),
        categoryId: '',
        basePrice: Number(p.default_variant?.price || 0),
        imageCount: Number(p.image_count || (p.primary_image ? 1 : 0)),
        variantCount: Number(p.variant_count || (p.default_variant ? 1 : 0)),
        hasActiveOffer: Boolean(p.has_active_offer),
        status: p.is_active ? 'Active' : 'Draft',
        attributes: [],
        infoItems: [],
        variations: [],
        media: p.primary_image
          ? [
              {
                id: `LIST-MEDIA-${p.id}`,
                url: normalizeAssetUrl(p.primary_image),
                altText: '',
                isPrimary: true,
                sortOrder: 0,
                persisted: true,
              },
            ]
          : [],
      }));

      setProducts(mappedProducts);
      setCategories(
        categoryRows.map((c: any) => ({
          id: String(c.id),
          name: String(c.name || categoryMap.get(String(c.id)) || ''),
        }))
      );
      setGlobalAttributes(
        globalAttributeRows.map((a: any) => ({
          id: String(a.id),
          name: String(a.name || ''),
          options: Array.isArray(a.options) ? a.options.map((opt: any) => String(opt)) : [],
        }))
      );
      if (productsRes.status === 'rejected') {
        console.error('Failed to load products', productsRes.reason);
      }
      if (categoriesRes.status === 'rejected') {
        console.error('Failed to load categories', categoriesRes.reason);
      }
      if (attributesRes.status === 'rejected') {
        console.warn('Failed to load global attributes. Product list still loaded.', attributesRes.reason);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCatalog();
  }, []);

  useEffect(() => {
    return () => {
      if (flashTimeoutRef.current) {
        window.clearTimeout(flashTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (!categoryDropdownRef.current) return;
      if (!categoryDropdownRef.current.contains(event.target as Node)) {
        setIsCategoryDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const filteredCategoryOptions = useMemo(() => {
    const q = categorySearch.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter((c) => c.name.toLowerCase().includes(q));
  }, [categories, categorySearch]);

  const columns = [
    { header: 'ID', accessorKey: 'id', className: 'text-xs text-muted-foreground w-20' },
    {
      header: 'Product Name',
      accessorKey: 'name',
      cell: (item: Product) => <div className="font-bold text-foreground">{item.name}</div>,
    },
    {
      header: 'Variations',
      accessorKey: 'variations',
      cell: (item: Product) => (
        <Badge variant="surface" className="text-[10px]">{item.variantCount || 0} total</Badge>
      ),
    },
    {
      header: 'Images',
      accessorKey: 'media',
      cell: (item: Product) => (
        <Badge variant="outline" className="text-[10px]">{Number(item.imageCount || item.media.length || 0)} images</Badge>
      ),
    },
    {
      header: 'Base Price',
      accessorKey: 'basePrice',
      align: 'right' as const,
      cell: (item: Product) => formatCurrency(item.basePrice),
    },
    {
      header: 'Offer',
      accessorKey: 'hasActiveOffer',
      align: 'center' as const,
      cell: (item: Product) => (
        item.hasActiveOffer ? (
          <Badge variant="surface" className="bg-emerald-50 text-emerald-700 border-emerald-100 font-bold text-[10px] uppercase tracking-wider">Active Offer</Badge>
        ) : (
          <span className="text-[10px] text-muted-foreground font-medium">None</span>
        )
      ),
    },
    {
      header: 'Status',
      accessorKey: 'status',
      align: 'right' as const,
      cell: (item: Product) => <StatusBadge status={item.status} type="generic" />,
    },
  ];

  const handleEdit = async (item: Product) => {
    const res = await catalogService.getProduct(item.id);
    const detail = mapDetailToProduct(res?.data as CatalogProductDetail);

    setEditingProduct(detail);
    setOriginalVariantIds(detail.variations.map((v) => v.id));
    setOriginalMediaIds(detail.media.map((m) => m.id));
    setOriginalAttributeIds(detail.attributes.map((a) => String(a.id)).filter(Boolean));
    setOriginalInfoItemIds(detail.infoItems.map((i) => i.id));
    setFormData({
      name: detail.name,
      description: detail.description,
      category: detail.category,
      categoryId: detail.categoryId,
      basePrice: detail.basePrice,
      status: detail.status,
      attributes: [...detail.attributes],
      infoItems: [...detail.infoItems],
      variations: [...detail.variations],
      media: [...detail.media],
    });
    setCategorySearch(detail.category || '');
    setIsCreatingAttr(false);
    setIsCreatingCategory(false);
    setNewCategoryName('');
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleAdd = () => {
    setEditingProduct(null);
    setOriginalVariantIds([]);
    setOriginalMediaIds([]);
    setOriginalAttributeIds([]);
    setOriginalInfoItemIds([]);
    setFormData({
      name: '',
      description: '',
      category: categories[0]?.name || '',
      categoryId: categories[0]?.id || '',
      basePrice: 0,
      status: 'Active',
      attributes: [],
      infoItems: [],
      variations: [],
      media: [],
    });
    setCategorySearch(categories[0]?.name || '');
    setIsCreatingAttr(false);
    setIsCreatingCategory(false);
    setNewCategoryName('');
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleCreateCategory = async () => {
    const name = newCategoryName.trim();
    if (!name) {
      setFormErrors((prev) => ({ ...prev, categoryName: 'Category name is required.' }));
      return;
    }
    clearError('categoryName');

    try {
      setIsSavingCategory(true);
      const created = await catalogService.createCategory({
        name,
        is_active: true,
      });

      const categoryRow = created?.data;
      if (!categoryRow?.id) {
        throw new Error('Category creation failed.');
      }

      const newCategory = {
        id: String(categoryRow.id),
        name: String(categoryRow.name || name),
      };

      setCategories((prev) => {
        if (prev.some((c) => c.id === newCategory.id)) return prev;
        return [...prev, newCategory];
      });

      setFormData((prev) => ({
        ...prev,
        categoryId: newCategory.id,
        category: newCategory.name,
      }));
      setCategorySearch(newCategory.name);

      setNewCategoryName('');
      setIsCreatingCategory(false);
      clearError('categoryName');
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to create category.';
      setFormErrors((prev) => ({ ...prev, categoryName: message }));
    } finally {
      setIsSavingCategory(false);
    }
  };

  const validateForm = (): boolean => {
    const errors: ProductFormErrors = {};

    if (!formData.name.trim()) {
      errors.name = 'Product name is required.';
    }

    if (!formData.categoryId) {
      errors.categoryId = 'Please select a category.';
    }

    if (!Number.isFinite(formData.basePrice) || formData.basePrice < 0) {
      errors.basePrice = 'Base price must be 0 or greater.';
    }

    if (formData.variations.length === 0) {
      errors.variations = 'Add at least one variation before saving.';
    }

    const variationById: Record<string, VariationFieldErrors> = {};
    formData.variations.forEach((variation) => {
      const rowError: VariationFieldErrors = {};
      if (!variation.sku.trim()) {
        rowError.sku = 'SKU is required.';
      }
      if (!Number.isFinite(variation.price) || variation.price <= 0) {
        rowError.price = 'Price must be greater than 0.';
      }
      const hasOfferPrice = typeof variation.offerPrice === 'number' && Number.isFinite(variation.offerPrice);
      if (variation.offerIsActive && !hasOfferPrice) {
        rowError.offer = 'Offer price is required when offer is active.';
      } else if (hasOfferPrice && variation.offerPrice! <= 0) {
        rowError.offer = 'Offer price must be greater than 0.';
      } else if (hasOfferPrice && Number.isFinite(variation.price) && variation.offerPrice! >= variation.price) {
        rowError.offer = 'Offer price must be lower than regular price.';
      }

      if (Object.keys(rowError).length > 0) {
        variationById[variation.id] = rowError;
      }
    });

    if (Object.keys(variationById).length > 0) {
      errors.variationById = variationById;
      errors.variations = errors.variations || 'Fix highlighted variation fields.';
    }

    setFormErrors(errors);
    if (Object.keys(errors).length > 0) {
      requestAnimationFrame(() => focusFirstError(errors));
    }
    return Object.keys(errors).length === 0;
  };

  const handleDelete = async (id: string) => {
    setDeleteProductError(null);
    setProductToDelete(id);
  };

  const openInventoryForVariant = (variation?: ProductVariation) => {
    const query = variation?.sku || formData.name || '';
    const target = query ? `/admin/inventory?search=${encodeURIComponent(query)}` : '/admin/inventory';
    setIsModalOpen(false);
    navigate(target);
  };

  const confirmDeleteProduct = async () => {
    if (!productToDelete) return;

    setIsDeletingProduct(true);
    setDeleteProductError(null);

    try {
      await catalogService.deleteProduct(productToDelete);
      setProductToDelete(null);
      await loadCatalog();
    } catch (error: any) {
      const responseData = error?.response?.data;
      const fallbackMessage = 'Unable to delete product right now. Please try again.';

      const message =
        (typeof responseData === 'string' && responseData) ||
        responseData?.detail ||
        responseData?.message ||
        (Array.isArray(responseData?.non_field_errors) ? responseData.non_field_errors[0] : '') ||
        error?.message ||
        fallbackMessage;

      setDeleteProductError(String(message || fallbackMessage));
    } finally {
      setIsDeletingProduct(false);
    }
  };

  const syncVariants = async (productId: string, attributeValueIdMap: Record<string, string>) => {
    const keptPersistedIds = new Set<string>();

    for (const v of formData.variations) {
      const attributeValueIds = Object.entries(v.attributes || {})
        .map(([attrName, attrValue]) => {
          const attrKey = normalizeKey(attrName || '');
          const valueKey = normalizeKey(String(attrValue || ''));
          if (!attrKey || !valueKey) return '';
          return attributeValueIdMap[`${attrKey}::${valueKey}`] || '';
        })
        .filter(Boolean);

      if (v.persisted) {
        keptPersistedIds.add(v.id);
        await catalogService.updateVariant(v.id, {
          sku: v.sku,
          price: v.price,
          is_default: v === formData.variations[0],
          name: Object.values(v.attributes).filter(Boolean).join(' / ') || v.sku,
          attribute_value_ids: attributeValueIds,
          offer_price: typeof v.offerPrice === 'number' ? v.offerPrice : null,
          offer_starts_at: v.offerStartsAt || null,
          offer_ends_at: v.offerEndsAt || null,
          offer_label: v.offerLabel || '',
          offer_is_active: Boolean(v.offerIsActive),
        });
      } else {
        const created = await catalogService.createVariant(productId, {
          sku: v.sku,
          price: v.price,
          is_default: formData.variations.indexOf(v) === 0,
          name: Object.values(v.attributes).filter(Boolean).join(' / ') || v.sku,
          attribute_value_ids: attributeValueIds,
          offer_price: typeof v.offerPrice === 'number' ? v.offerPrice : null,
          offer_starts_at: v.offerStartsAt || null,
          offer_ends_at: v.offerEndsAt || null,
          offer_label: v.offerLabel || '',
          offer_is_active: Boolean(v.offerIsActive),
        });
        const createdId = created?.data?.id;
        if (createdId) keptPersistedIds.add(String(createdId));
      }
    }

    for (const oldId of originalVariantIds) {
      if (!keptPersistedIds.has(oldId)) {
        try {
          await catalogService.deleteVariant(oldId);
        } catch {
          // Ignore "last variant" constraint errors silently for now.
        }
      }
    }
  };

  const syncAttributes = async (productId: string) => {
    const keptPersistedIds = new Set<string>();

    for (const attr of formData.attributes) {
      const payload = {
        global_attribute_id: attr.globalAttributeId,
        name: attr.name.trim(),
        options: attr.options.map((opt) => opt.trim()).filter(Boolean),
      };

      if (!payload.name) continue;

      if (attr.persisted && attr.id) {
        keptPersistedIds.add(attr.id);
        await catalogService.updateProductAttribute(productId, attr.id, payload);
      } else {
        const created = await catalogService.createProductAttribute(productId, payload);
        const createdId = created?.data?.id;
        if (createdId) {
          keptPersistedIds.add(String(createdId));
        }
      }
    }

    for (const oldId of originalAttributeIds) {
      if (!keptPersistedIds.has(oldId)) {
        await catalogService.deleteProductAttribute(productId, oldId);
      }
    }
  };

  const syncMedia = async (productId: string) => {
    const keptPersistedIds = new Set<string>();

    for (let i = 0; i < formData.media.length; i += 1) {
      const m = formData.media[i];
      if (m.persisted) {
        keptPersistedIds.add(m.id);
        await catalogService.updateProductMedia(productId, m.id, {
          alt_text: m.altText,
          is_primary: m.isPrimary,
          sort_order: i,
        });
      } else if (m.file) {
        const uploaded = await catalogService.uploadProductMedia(productId, m.file, {
          alt_text: m.altText,
          is_primary: m.isPrimary,
          sort_order: i,
        });
        const uploadedId = uploaded?.data?.id;
        if (uploadedId) keptPersistedIds.add(String(uploadedId));
      }
    }

    for (const oldId of originalMediaIds) {
      if (!keptPersistedIds.has(oldId)) {
        await catalogService.deleteProductMedia(productId, oldId);
      }
    }
  };

  const syncInfoItems = async (productId: string) => {
    const keptPersistedIds = new Set<string>();

    for (let i = 0; i < formData.infoItems.length; i += 1) {
      const row = formData.infoItems[i];
      const payload = {
        title: row.title.trim(),
        value: row.value.trim(),
        sort_order: i,
        is_active: row.isActive,
      };

      if (!payload.title || !payload.value) {
        continue;
      }

      if (row.persisted) {
        keptPersistedIds.add(row.id);
        await catalogService.updateProductInfoItem(productId, row.id, payload);
      } else {
        const created = await catalogService.createProductInfoItem(productId, payload);
        const createdId = created?.data?.id;
        if (createdId) keptPersistedIds.add(String(createdId));
      }
    }

    for (const oldId of originalInfoItemIds) {
      if (!keptPersistedIds.has(oldId)) {
        await catalogService.deleteProductInfoItem(productId, oldId);
      }
    }

    await catalogService.reorderProductInfoItems(
      productId,
      formData.infoItems.map((item, index) => ({ id: item.id, sort_order: index })).filter((item) => !item.id.startsWith('temp-info-'))
    );
  };

  const addInfoItem = () => {
    const id = `temp-info-${Date.now()}`;
    setFormData((prev) => ({
      ...prev,
      infoItems: [
        ...prev.infoItems,
        { id, title: '', value: '', sortOrder: prev.infoItems.length, isActive: true, persisted: false },
      ],
    }));
  };

  const updateInfoItem = (id: string, patch: Partial<ProductInfoItemRow>) => {
    setFormData((prev) => ({
      ...prev,
      infoItems: prev.infoItems.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    }));
  };

  const removeInfoItem = (id: string) => {
    setFormData((prev) => ({
      ...prev,
      infoItems: prev.infoItems.filter((item) => item.id !== id).map((item, index) => ({ ...item, sortOrder: index })),
    }));
  };

  const onInfoItemsDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    setFormData((prev) => {
      const oldIndex = prev.infoItems.findIndex((item) => item.id === active.id);
      const newIndex = prev.infoItems.findIndex((item) => item.id === over.id);
      if (oldIndex < 0 || newIndex < 0) return prev;
      const moved = arrayMove(prev.infoItems, oldIndex, newIndex).map((item, index) => ({
        ...item,
        sortOrder: index,
      }));
      return { ...prev, infoItems: moved };
    });
  };

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setIsSaving(true);
      let productId = editingProduct?.id || '';

      if (editingProduct) {
        await catalogService.updateProduct(editingProduct.id, {
          name: formData.name,
          category_id: formData.categoryId,
          description: formData.description,
          is_active: formData.status === 'Active',
        });
      } else {
        const created = await catalogService.createProduct({
          name: formData.name,
          category_id: formData.categoryId,
          is_active: formData.status === 'Active',
          short_description: '',
          description: formData.description,
        });
        productId = String(created?.data?.id || '');
      }

      if (!productId) {
        throw new Error('Unable to resolve product id after save.');
      }

      await syncAttributes(productId);
      const refreshed = await catalogService.getProduct(productId);
      const detailForIds = refreshed?.data as CatalogProductDetail;
      const attributeValueIdMap = buildAttributeValueIdMap(detailForIds);
      await syncVariants(productId, attributeValueIdMap);
      await syncMedia(productId);
      await syncInfoItems(productId);

      setIsModalOpen(false);
      await loadCatalog();
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to save product.';
      alert(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddGlobalAttribute = (ga: { id: string; name: string; options: string[] }) => {
    setFormData((prev) => ({
      ...prev,
      attributes: [...prev.attributes, { globalAttributeId: ga.id, name: ga.name, options: [...ga.options] }],
    }));
  };

  const handleCreateNewGlobalAttribute = async () => {
    if (!newAttrData.name.trim()) return;
    const parsedOptions = newAttrData.options.split(',').map((s) => s.trim()).filter(Boolean);
    try {
      const created = await catalogService.createAttribute({
        name: newAttrData.name.trim(),
        options: parsedOptions,
        is_active: true,
      });
      const row = created?.data;
      if (!row?.id) return;
      const newGa = {
        id: String(row.id),
        name: String(row.name || newAttrData.name.trim()),
        options: Array.isArray(row.options) ? row.options.map((o: any) => String(o)) : parsedOptions,
      };
      setGlobalAttributes((prev) => {
        if (prev.some((attr) => attr.id === newGa.id)) return prev;
        return [...prev, newGa];
      });
      setFormData((prev) => ({
        ...prev,
        attributes: [...prev.attributes, { globalAttributeId: newGa.id, name: newGa.name, options: [...newGa.options] }],
      }));
      setIsCreatingAttr(false);
      setNewAttrData({ name: '', options: '' });
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to create global attribute.';
      alert(message);
    }
  };

  const updateAttribute = (index: number, value: string) => {
    const next = [...formData.attributes];
    next[index].options = value.split(',').map((s) => s.trim()).filter(Boolean);
    setFormData((prev) => ({ ...prev, attributes: next }));
  };

  const removeAttribute = async (index: number) => {
    const target = formData.attributes[index];
    if (!target) return;

    // If this is an existing product attribute, delete immediately in backend.
    if (editingProduct?.id && target.persisted && target.id) {
      try {
        await catalogService.deleteProductAttribute(editingProduct.id, target.id);
        setOriginalAttributeIds((prev) => prev.filter((id) => id !== target.id));
      } catch (error: any) {
        const message = error?.response?.data?.message || 'Failed to delete attribute.';
        alert(message);
        return;
      }
    }

    const next = [...formData.attributes];
    next.splice(index, 1);
    setFormData((prev) => ({ ...prev, attributes: next }));
  };

  const generateVariations = () => {
    if (formData.attributes.length === 0) return;
    const arrays = formData.attributes.map((a) => a.options);
    if (arrays.some((x) => x.length === 0)) {
      alert('All attributes must have at least one option.');
      return;
    }

    const cartesian = (acc: string[][], cur: string[]): string[][] => {
      if (!acc.length) return cur.map((v) => [v]);
      return acc.flatMap((prev) => cur.map((v) => [...prev, v]));
    };
    const combos = arrays.reduce(cartesian, [] as string[][]);

    const generated: ProductVariation[] = combos.map((combo, i) => {
      const attrs: Record<string, string> = {};
      formData.attributes.forEach((attr, idx) => {
        attrs[attr.name] = combo[idx];
      });
      const skuSuffix = combo.join('-').toUpperCase().replace(/\s+/g, '');
      return {
        id: `temp-var-${Date.now()}-${i}`,
        sku: `${formData.name.substring(0, 3).toUpperCase() || 'PRD'}-${skuSuffix}`,
        attributes: attrs,
        price: formData.basePrice,
        offerPrice: null,
        offerStartsAt: '',
        offerEndsAt: '',
        offerLabel: '',
        offerIsActive: false,
        persisted: false,
      };
    });

    setFormData((prev) => ({ ...prev, variations: generated }));
    clearError('variations');
    setFormErrors((prev) => ({ ...prev, variationById: {} }));
  };

  const addManualVariation = () => {
    const newVariationId = `temp-var-${Date.now()}`;
    setFormData((prev) => ({
      ...prev,
      variations: [
        ...prev.variations,
        {
          id: newVariationId,
          sku: 'NEW-SKU',
          attributes: {},
          price: prev.basePrice,
          offerPrice: null,
          offerStartsAt: '',
          offerEndsAt: '',
          offerLabel: '',
          offerIsActive: false,
          persisted: false,
        },
      ],
    }));
    clearError('variations');
  };

  const updateVariation = (index: number, field: string, value: any, isAttr = false) => {
    const next = [...formData.variations];
    if (isAttr) next[index].attributes[field] = value;
    else (next[index] as any)[field] = value;
    setFormData((prev) => ({ ...prev, variations: next }));

    if (!isAttr) {
      const variationId = next[index]?.id;
      if (variationId) {
        if (field === 'sku') clearVariationError(variationId, 'sku');
        if (field === 'price') clearVariationError(variationId, 'price');
        if (field === 'offerPrice' || field === 'offerIsActive') clearVariationError(variationId, 'offer');
      }
    }
  };

  const updateVariationDateTimePart = (
    index: number,
    field: 'offerStartsAt' | 'offerEndsAt',
    part: 'date' | 'time',
    value: string
  ) => {
    const currentIso = (formData.variations[index]?.[field] as string) || '';
    const currentDate = toLocalDateInput(currentIso);
    const currentTime = toLocalTimeInput(currentIso) || '00:00';

    const nextDate = part === 'date' ? value : currentDate;
    const nextTime = part === 'time' ? value : currentTime;

    const nextIso = nextDate ? localDateTimeToIso(nextDate, nextTime) : '';
    updateVariation(index, field, nextIso);
  };

  const removeVariation = (index: number) => {
    const targetId = formData.variations[index]?.id;
    const next = [...formData.variations];
    next.splice(index, 1);
    setFormData((prev) => ({ ...prev, variations: next }));

    if (targetId) {
      setFormErrors((prev) => {
        const variationById = { ...(prev.variationById || {}) };
        delete variationById[targetId];
        return { ...prev, variationById };
      });
    }
  };

  const handleMediaSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const validFiles = Array.from(files).filter((file) => {
      if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        alert(`Unsupported file type: ${file.name}. Only JPG, PNG, and WEBP are allowed.`);
        return false;
      }
      if (file.size > MAX_IMAGE_SIZE_BYTES) {
        alert(`File too large: ${file.name}. Max allowed size is 5 MB.`);
        return false;
      }
      return true;
    });
    if (validFiles.length === 0) {
      return;
    }

    const added = validFiles.map((file, index) => ({
      id: `temp-media-${Date.now()}-${index}`,
      url: URL.createObjectURL(file),
      altText: file.name.replace(/\.[^/.]+$/, ''),
      isPrimary: false,
      sortOrder: formData.media.length + index,
      file,
      persisted: false,
    }));
    setFormData((prev) => {
      const next = [...prev.media, ...added];
      if (!next.some((m) => m.isPrimary) && next.length > 0) next[0].isPrimary = true;
      return { ...prev, media: next };
    });
  };

  const handleDropMedia = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOverUploader(false);
    handleMediaSelect(event.dataTransfer.files);
  };

  const removeMedia = (mediaId: string) => {
    setFormData((prev) => {
      const target = prev.media.find((m) => m.id === mediaId);
      if (target?.url.startsWith('blob:')) URL.revokeObjectURL(target.url);
      const next = prev.media.filter((m) => m.id !== mediaId);
      if (next.length > 0 && !next.some((m) => m.isPrimary)) next[0].isPrimary = true;
      return { ...prev, media: next };
    });
  };

  const setPrimaryMedia = (mediaId: string) => {
    setFormData((prev) => ({
      ...prev,
      media: prev.media.map((m) => ({ ...m, isPrimary: m.id === mediaId })),
    }));
  };

  const updateMediaAltText = (mediaId: string, altText: string) => {
    setFormData((prev) => ({
      ...prev,
      media: prev.media.map((m) => (m.id === mediaId ? { ...m, altText } : m)),
    }));
  };

  const filteredProducts = useMemo(
    () =>
      products.filter(
        (p) => {
          const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                               p.id.toLowerCase().includes(searchTerm.toLowerCase());
          
          if (!matchesSearch) return false;
          
          if (offerFilter === 'active') return p.hasActiveOffer;
          if (offerFilter === 'none') return !p.hasActiveOffer;
          return true;
        }
      ),
    [products, searchTerm, offerFilter]
  );

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, offerFilter, rowsPerPage]);

  const totalPages = Math.max(1, Math.ceil(filteredProducts.length / rowsPerPage));
  const safePage = Math.min(currentPage, totalPages);
  const paginatedProducts = useMemo(() => {
    const start = (safePage - 1) * rowsPerPage;
    return filteredProducts.slice(start, start + rowsPerPage);
  }, [filteredProducts, safePage, rowsPerPage]);

  const actions = (item: Product) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[160px]">
        <DropdownMenuItem onClick={() => handleEdit(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Edit size={14} /> Edit Product
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleDelete(item.id)} className="flex items-center gap-2 cursor-pointer text-xs text-destructive focus:text-destructive">
          <Trash2 size={14} /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Products</h1>
          <p className="text-xs text-muted-foreground mt-1">Manage your catalog, attributes, and variations.</p>
        </div>
        <Button onClick={handleAdd} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm">
          <Plus size={16} /> Add Product
        </Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col sm:flex-row gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative group min-w-[240px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  placeholder="Search products by name or ID..."
                  className="pl-9 h-10 border-border/60 bg-white/50 focus:bg-white shadow-sm transition-all"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <div className="flex items-center gap-2 bg-muted/30 p-1 rounded-lg border border-border/40">
                <button
                  onClick={() => setOfferFilter('all')}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                    offerFilter === 'all' 
                      ? 'bg-white text-primary shadow-sm' 
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  All
                </button>
                <button
                  onClick={() => setOfferFilter('active')}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                    offerFilter === 'active' 
                      ? 'bg-emerald-50 text-emerald-700 shadow-sm' 
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Active Offers
                </button>
                <button
                  onClick={() => setOfferFilter('none')}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                    offerFilter === 'none' 
                      ? 'bg-white text-primary shadow-sm' 
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  No Offers
                </button>
              </div>
            </div>
          </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">
          Loading products...
        </div>
      ) : (
        <div className="space-y-3">
          <DataTable data={paginatedProducts} columns={columns} actions={actions} onRowClick={(item) => handleEdit(item)} />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between rounded-[14px] border border-border bg-white px-3 py-2">
            <div className="text-xs text-muted-foreground">
              Showing {filteredProducts.length === 0 ? 0 : (safePage - 1) * rowsPerPage + 1}
              {' '}-{' '}
              {Math.min(safePage * rowsPerPage, filteredProducts.length)} of {filteredProducts.length}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <label className="text-xs text-muted-foreground">Rows</label>
                <select
                  value={rowsPerPage}
                  onChange={(e) => setRowsPerPage(Number(e.target.value))}
                  className="h-8 rounded-md border border-border bg-white px-2 text-xs"
                >
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                >
                  Prev
                </Button>
                <span className="text-xs text-muted-foreground px-2">
                  Page {safePage} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      <Modal open={isModalOpen} onOpenChange={setIsModalOpen}>
        <ModalContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
          <ModalHeader>
            <ModalTitle>{editingProduct ? 'Edit Product' : 'Add New Product'}</ModalTitle>
          </ModalHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 py-4">
            <div className="space-y-6">
              <div className="space-y-4 rounded-xl border border-border/80 bg-white p-4">
                <h3 className="font-bold text-sm text-foreground">Basic Info</h3>
                <div ref={nameFieldRef} className="grid gap-2">
                  <label className="text-sm font-medium">Product Name</label>
                  <Input
                    value={formData.name}
                    onChange={(e) => {
                      setFormData({ ...formData, name: e.target.value });
                      clearError('name');
                    }}
                    placeholder="e.g. Diamond Ring"
                    className={formErrors.name ? 'border-destructive focus-visible:ring-destructive/30' : ''}
                  />
                  {formErrors.name ? <p className="text-[11px] text-destructive">{formErrors.name}</p> : null}
                </div>
                <div className="grid grid-cols-2 gap-4 items-start">
                  <div ref={categoryFieldRef} className="grid gap-2">
                    <div className="flex items-center justify-between gap-2">
                      <label className="text-sm font-medium">Category</label>
                      {!isCreatingCategory ? (
                        <button
                          type="button"
                          className="text-xs font-medium text-muted-foreground underline decoration-dotted underline-offset-4 transition-colors hover:text-primary"
                          onClick={() => setIsCreatingCategory(true)}
                        >
                          + Add Category
                        </button>
                      ) : null}
                    </div>
                    <div ref={categoryDropdownRef} className="relative">
                      <Input
                        value={categorySearch}
                        onFocus={() => setIsCategoryDropdownOpen(true)}
                        onChange={(e) => {
                          const value = e.target.value;
                          setCategorySearch(value);
                          setIsCategoryDropdownOpen(true);
                          const exact = categories.find((c) => c.name.toLowerCase() === value.trim().toLowerCase());
                          setFormData((prev) => ({
                            ...prev,
                            categoryId: exact?.id || '',
                            category: exact?.name || value,
                          }));
                          if (exact) clearError('categoryId');
                        }}
                        placeholder="Search category..."
                        className={formErrors.categoryId ? 'border-destructive focus-visible:ring-destructive/30' : ''}
                      />
                      {isCategoryDropdownOpen ? (
                        <div className="absolute z-30 mt-1 w-full rounded-md border border-border bg-white shadow-lg max-h-48 overflow-y-auto">
                          {filteredCategoryOptions.length === 0 ? (
                            <div className="px-3 py-2 text-xs text-muted-foreground">No matching categories</div>
                          ) : (
                            filteredCategoryOptions.map((c) => (
                              <button
                                key={c.id}
                                type="button"
                                className="w-full text-left px-3 py-2 text-sm hover:bg-muted/40 transition-colors"
                                onClick={() => {
                                  setFormData((prev) => ({ ...prev, categoryId: c.id, category: c.name }));
                                  setCategorySearch(c.name);
                                  setIsCategoryDropdownOpen(false);
                                  clearError('categoryId');
                                }}
                              >
                                {c.name}
                              </button>
                            ))
                          )}
                        </div>
                      ) : null}
                    </div>
                    {formErrors.categoryId ? <p className="text-[11px] text-destructive">{formErrors.categoryId}</p> : null}
                  </div>
                  <div ref={basePriceFieldRef} className="grid gap-2">
                    <label className="text-sm font-medium">Base Price ({displayCurrency})</label>
                    <Input
                      type="number"
                      value={formData.basePrice}
                      onChange={(e) => {
                        setFormData({ ...formData, basePrice: parseFloat(e.target.value) || 0 });
                        clearError('basePrice');
                      }}
                      className={formErrors.basePrice ? 'border-destructive focus-visible:ring-destructive/30' : ''}
                    />
                    {formErrors.basePrice ? <p className="text-[11px] text-destructive">{formErrors.basePrice}</p> : null}
                  </div>
                </div>
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Description</label>
                  <LexicalHtmlEditor
                    value={formData.description}
                    onChange={(html) => setFormData((prev) => ({ ...prev, description: html }))}
                    placeholder="Write rich product description..."
                  />
                </div>
                {isCreatingCategory ? (
                  <div className="rounded-lg border border-primary/20 bg-primary/5 p-2 space-y-2">
                    <Input
                      placeholder="Category name"
                      value={newCategoryName}
                      onChange={(e) => {
                        setNewCategoryName(e.target.value);
                        clearError('categoryName');
                      }}
                      className={`h-8 text-xs bg-white ${formErrors.categoryName ? 'border-destructive focus-visible:ring-destructive/30' : ''}`}
                    />
                    {formErrors.categoryName ? <p className="text-[11px] text-destructive">{formErrors.categoryName}</p> : null}
                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => {
                          setIsCreatingCategory(false);
                          setNewCategoryName('');
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={handleCreateCategory}
                        disabled={isSavingCategory}
                      >
                        {isSavingCategory ? 'Saving...' : 'Save Category'}
                      </Button>
                    </div>
                  </div>
                ) : null}
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Status</label>
                  <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })}>
                    <option value="Active">Active</option>
                    <option value="Draft">Draft</option>
                  </select>
                </div>
              </div>

              <div className="space-y-4 rounded-xl border border-border/80 bg-white p-4">
                <div className="flex items-center justify-between border-b pb-2">
                  <h3 className="font-bold text-sm text-foreground">Product Images</h3>
                  <Badge variant="surface" className="text-[10px]">{formData.media.length} uploaded</Badge>
                </div>
                <div className="grid gap-2">
                  <label className="text-sm font-medium">Upload Images</label>
                  <input
                    ref={mediaInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    onChange={(e) => handleMediaSelect(e.target.files)}
                    className="hidden"
                  />
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragOverUploader(true);
                    }}
                    onDragLeave={() => setIsDragOverUploader(false)}
                    onDrop={handleDropMedia}
                    onClick={() => mediaInputRef.current?.click()}
                    className={[
                      'rounded-xl border-2 border-dashed p-5 cursor-pointer transition-all duration-300',
                      isDragOverUploader
                        ? 'border-primary bg-primary/10'
                        : 'border-border bg-muted/20 hover:border-primary/50 hover:bg-muted/30',
                    ].join(' ')}
                  >
                    <div className="text-center space-y-2">
                      <p className="text-sm font-semibold text-foreground">Drag and drop product images here</p>
                      <p className="text-xs text-muted-foreground">or click to browse files</p>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[260px] overflow-y-auto pr-1">
                  {formData.media.map((media) => (
                    <div key={media.id} className="rounded-xl border border-border bg-white p-2 shadow-sm">
                      <div className="relative">
                        <img src={media.url} alt={media.altText || 'Product image'} className="h-28 w-full rounded-md object-cover border border-border/60" />
                        {media.isPrimary ? (
                          <span className="absolute top-2 left-2 rounded-full bg-primary text-white text-[10px] font-bold px-2 py-0.5">
                            Primary
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 space-y-2">
                        <Input
                          value={media.altText}
                          onChange={(e) => updateMediaAltText(media.id, e.target.value)}
                          placeholder="Alt text"
                          className="h-8 text-xs"
                        />
                        <div className="flex items-center justify-between gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-7 px-2 text-[10px]"
                            onClick={() => setPrimaryMedia(media.id)}
                            disabled={media.isPrimary}
                          >
                            {media.isPrimary ? 'Selected' : 'Set Primary'}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-[10px] text-destructive"
                            onClick={() => removeMedia(media.id)}
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                  {formData.media.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-center text-xs text-muted-foreground sm:col-span-2">
                      No product images uploaded yet.
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="space-y-4 rounded-xl border border-border/80 bg-white p-4">
                <div className="flex items-center justify-between border-b pb-2">
                  <h3 className="font-bold text-sm text-foreground">Attributes</h3>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-7 text-xs px-2"><Plus size={14} className="mr-1" /> Add</Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {globalAttributes.filter((ga) => !formData.attributes.find((pa) => pa.name === ga.name)).map((ga) => (
                        <DropdownMenuItem onClick={() => handleAddGlobalAttribute(ga)} key={ga.id} className="cursor-pointer">
                          {ga.name}
                        </DropdownMenuItem>
                      ))}
                      <div className="h-px bg-border my-1" />
                      <DropdownMenuItem onClick={() => setIsCreatingAttr(true)} className="cursor-pointer text-primary font-bold">
                        <Plus size={14} className="mr-2" /> Create New
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                {isCreatingAttr ? (
                  <div className="bg-primary/5 p-3 rounded-xl border border-primary/20 space-y-3">
                    <Input placeholder="Name (e.g. Material)" value={newAttrData.name} onChange={(e) => setNewAttrData({ ...newAttrData, name: e.target.value })} className="h-8 text-xs bg-white" />
                    <Input placeholder="Options (e.g. Gold, Silver)" value={newAttrData.options} onChange={(e) => setNewAttrData({ ...newAttrData, options: e.target.value })} className="h-8 text-xs bg-white" />
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setIsCreatingAttr(false)}>Cancel</Button>
                      <Button size="sm" className="h-7 text-xs" onClick={handleCreateNewGlobalAttribute}>Save & Add</Button>
                    </div>
                  </div>
                ) : null}

                {formData.attributes.map((attr, i) => (
                  <div key={i} className="flex gap-2 items-start rounded-lg border border-border/70 bg-white p-3">
                    <div className="h-8 text-xs flex items-center font-semibold px-2 w-1/3 rounded-md bg-muted/20">{attr.name}</div>
                    <div className="grid gap-2 w-full">
                      <Input placeholder="Options (comma separated)" value={attr.options.join(', ')} onChange={(e) => updateAttribute(i, e.target.value)} className="h-8 text-xs bg-white" />
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => removeAttribute(i)} className="h-8 w-8 p-0 text-destructive shrink-0"><Trash2 size={14} /></Button>
                  </div>
                ))}
                {formData.attributes.length === 0 && !isCreatingAttr ? (
                  <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-xs text-muted-foreground">
                    Add attributes and options here. These can be used to generate variations.
                  </div>
                ) : null}
                {formData.attributes.length > 0 ? (
                  <div className="grid grid-cols-1 gap-2">
                    <Button
                      variant="outline"
                      className="w-full text-xs h-8 shadow-sm"
                      onClick={generateVariations}
                    >
                      Generate Variations
                    </Button>
                  </div>
                ) : null}
              </div>

              <div className="space-y-4 rounded-xl border border-border/80 bg-white p-4">
                <div className="flex items-center justify-between border-b pb-2">
                  <h3 className="font-bold text-sm text-foreground">Additional Information</h3>
                  <Button type="button" variant="ghost" size="sm" className="h-7 text-xs px-2" onClick={addInfoItem}>
                    <Plus size={14} className="mr-1" /> Add Row
                  </Button>
                </div>
                {formData.infoItems.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-xs text-muted-foreground">
                    Add title/value rows. These will appear under the "Additional Information" tab on product page.
                  </div>
                ) : (
                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onInfoItemsDragEnd}>
                    <SortableContext items={formData.infoItems.map((item) => item.id)} strategy={verticalListSortingStrategy}>
                      <div className="space-y-2">
                        {formData.infoItems.map((item) => (
                          <SortableInfoItemRow
                            key={item.id}
                            item={item}
                            onUpdate={updateInfoItem}
                            onDelete={removeInfoItem}
                          />
                        ))}
                      </div>
                    </SortableContext>
                  </DndContext>
                )}
              </div>
            </div>

              <div ref={variationsSectionRef} className={`space-y-4 rounded-xl border bg-white p-4 ${formErrors.variations ? 'border-destructive/60' : 'border-border/80'}`}>
                <div className="flex items-center justify-between border-b pb-2">
                  <h3 className="font-bold text-sm text-foreground">Variations ({formData.variations.length})</h3>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openInventoryForVariant(formData.variations[0])}
                      className="h-7 text-xs px-2 border-primary/50 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
                    >
                      Manage Stock
                    </Button>
                    <Button variant="ghost" size="sm" onClick={addManualVariation} className="h-7 text-xs px-2"><Plus size={14} className="mr-1" /> Add Manual</Button>
                  </div>
                </div>
                {formErrors.variations ? <p className="text-[11px] text-destructive -mt-1">{formErrors.variations}</p> : null}

              <div className="space-y-2 max-h-[560px] min-h-[220px] overflow-y-auto pr-2">
                {formData.variations.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-xs text-muted-foreground">
                    Add variations manually or generate them from attributes.
                  </div>
                ) : formData.variations.map((v, i) => (
                  <div
                    key={v.id}
                    ref={(node) => {
                      variationRowRefs.current[v.id] = node;
                    }}
                    className={`bg-white border p-3 rounded-xl space-y-3 relative group shadow-sm ${(formErrors.variationById?.[v.id] ? 'border-destructive/60' : 'border-border')}`}
                  >
                    <Button variant="ghost" size="sm" onClick={() => removeVariation(i)} className="absolute top-2 right-2 h-6 w-6 p-0 text-destructive opacity-0 group-hover:opacity-100 transition-opacity">
                      <Trash2 size={14} />
                    </Button>
                    <div className="grid grid-cols-2 gap-2 pr-6">
                      <Input
                        placeholder="SKU"
                        value={v.sku}
                        onChange={(e) => updateVariation(i, 'sku', e.target.value)}
                        className={`h-7 text-xs ${(formErrors.variationById?.[v.id]?.sku ? 'border-destructive focus-visible:ring-destructive/30' : '')}`}
                      />
                      <Input
                        type="number"
                        placeholder="Price"
                        value={v.price}
                        onChange={(e) => updateVariation(i, 'price', parseFloat(e.target.value) || 0)}
                        className={`h-7 text-xs ${(formErrors.variationById?.[v.id]?.price ? 'border-destructive focus-visible:ring-destructive/30' : '')}`}
                      />
                    </div>
                    <p className="text-[10px] text-muted-foreground -mt-1">
                      Stock is managed from Inventory module (warehouse-wise).
                    </p>
                    <div className="grid grid-cols-2 gap-2 pr-6">
                      <Input
                        type="number"
                        placeholder="Offer Price"
                        value={typeof v.offerPrice === 'number' ? v.offerPrice : ''}
                        onChange={(e) => updateVariation(i, 'offerPrice', e.target.value ? parseFloat(e.target.value) : null)}
                        className={`h-7 text-xs ${(formErrors.variationById?.[v.id]?.offer ? 'border-destructive focus-visible:ring-destructive/30' : '')}`}
                      />
                      <Input
                        placeholder="Offer Label"
                        value={v.offerLabel || ''}
                        onChange={(e) => updateVariation(i, 'offerLabel', e.target.value)}
                        className="h-7 text-xs"
                      />
                    </div>
                    <div className="grid grid-cols-1 gap-2 pr-6">
                      <div className="grid grid-cols-2 gap-2">
                        <div className="rounded-md border border-border/70 bg-muted/20 p-2 space-y-1.5">
                          <p className="text-[10px] font-medium text-muted-foreground">Offer Starts</p>
                          <Input
                            type="date"
                            value={toLocalDateInput(v.offerStartsAt || '')}
                            onChange={(e) => updateVariationDateTimePart(i, 'offerStartsAt', 'date', e.target.value)}
                            className="h-8 text-xs w-full"
                          />
                          <Input
                            type="time"
                            step={60}
                            value={toLocalTimeInput(v.offerStartsAt || '')}
                            onChange={(e) => updateVariationDateTimePart(i, 'offerStartsAt', 'time', e.target.value)}
                            className="h-8 text-xs w-full"
                          />
                        </div>
                        <div className="rounded-md border border-border/70 bg-muted/20 p-2 space-y-1.5">
                          <p className="text-[10px] font-medium text-muted-foreground">Offer Ends</p>
                          <Input
                            type="date"
                            value={toLocalDateInput(v.offerEndsAt || '')}
                            onChange={(e) => updateVariationDateTimePart(i, 'offerEndsAt', 'date', e.target.value)}
                            className="h-8 text-xs w-full"
                          />
                          <Input
                            type="time"
                            step={60}
                            value={toLocalTimeInput(v.offerEndsAt || '')}
                            onChange={(e) => updateVariationDateTimePart(i, 'offerEndsAt', 'time', e.target.value)}
                            className="h-8 text-xs w-full"
                          />
                        </div>
                      </div>
                    </div>
                    <label className="inline-flex items-center gap-2 text-[11px] text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={Boolean(v.offerIsActive)}
                        onChange={(e) => updateVariation(i, 'offerIsActive', e.target.checked)}
                      />
                      Offer active
                    </label>
                    {formErrors.variationById?.[v.id]?.sku ? <p className="text-[11px] text-destructive -mt-1">{formErrors.variationById?.[v.id]?.sku}</p> : null}
                    {formErrors.variationById?.[v.id]?.price ? <p className="text-[11px] text-destructive -mt-1">{formErrors.variationById?.[v.id]?.price}</p> : null}
                    {formErrors.variationById?.[v.id]?.offer ? <p className="text-[11px] text-destructive -mt-1">{formErrors.variationById?.[v.id]?.offer}</p> : null}
                    <div className="flex flex-wrap gap-2 truncate">
                      {formData.attributes.map((attr, aIndex) => (
                        <div key={aIndex} className="flex items-center gap-1.5 text-[10px] bg-muted/30 px-2 py-1 rounded-md">
                          <span className="text-muted-foreground font-medium">{attr.name}:</span>
                          <Input className="h-5 w-16 text-[10px] px-1 py-0 shadow-none border-border/50 bg-white" value={v.attributes[attr.name] || ''} onChange={(e) => updateVariation(i, attr.name, e.target.value, true)} placeholder="Value" />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
                {formData.variations.length === 0 ? (
                  <div className="text-center p-8 text-muted-foreground text-xs bg-muted/20 rounded-xl border border-dashed border-border flex min-h-[180px] flex-col items-center justify-center gap-3">
                    <span>No variations defined yet.</span>
                    <Button variant="outline" size="sm" className="h-7 text-xs" onClick={addManualVariation}>
                      + Add Manual Variation
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <ModalFooter className="border-t pt-4">
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save Product'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <ConfirmDialog
        open={Boolean(productToDelete)}
        onOpenChange={(open) => {
          if (!open) {
            setProductToDelete(null);
            setDeleteProductError(null);
          }
        }}
        title="Delete Product"
        description={
          deleteProductError
            ? `Delete failed: ${deleteProductError}`
            : 'This product will be removed from active catalog listings.'
        }
        confirmLabel="Delete Product"
        variant="destructive"
        onConfirm={confirmDeleteProduct}
        loading={isDeletingProduct}
      />
    </div>
  );
};
