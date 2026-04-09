import React, { useEffect, useMemo, useRef, useState } from 'react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Search, Filter, RefreshCw, Eye, Trash2, MoreHorizontal, Plus, FileDown, RotateCw, Mail, Printer } from 'lucide-react';
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
import ordersService, { type AdminOrderDetail, type AdminOrderListRow } from '@/services/api/orders';
import shippingService from '@/services/api/shipping';
import paymentsService, { type AdminPaymentTransaction } from '@/services/api/payments';
import inventoryService from '@/services/api/inventory';
import customerService from '@/services/api/customers';
import { useCurrency } from '@/hooks/useCurrency';
import type { Customer, AddressData } from '@/types/customer';

const extractRows = (payload: any): any[] => {
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.data?.results)) return payload.data.results;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload)) return payload;
  return [];
};

const statusOptions = ['draft', 'placed', 'paid', 'processing', 'shipped', 'delivered', 'completed', 'cancelled', 'refunded'];
const paymentStatusOptions = ['pending', 'paid', 'failed', 'refunded', 'partially_refunded'];
const paymentMethodOptions = ['cod', 'cashfree', 'razorpay', 'phonepe', 'stripe', 'upi', 'bank_transfer'];

const toTitle = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

type UiToast = {
  id: string;
  variant: 'success' | 'error';
  message: string;
};

interface VariantOption {
  id: string;
  sku: string;
  name: string;
  product_name: string;
  is_active: boolean;
  price?: string;
}

interface DraftOrderItem {
  variant_id: string;
  sku: string;
  product_name: string;
  variant_name: string;
  unit_price: number;
  quantity: number;
}

interface PaymentTxnView {
  id: string;
  provider: string;
  provider_ref: string;
  status: string;
  amount: number;
  currency: string;
  created_at: string;
  razorpay_payment_id?: string;
  razorpay_order_id?: string;
}

interface OrderFormState {
  guest_email: string;
  status: string;
  payment_status: string;
  payment_method: string;
  subtotal: number;
  discount_amount: number;
  shipping_cost: number;
  tax_amount: number;
  grand_total: number;
  currency: string;
  coupon_code: string;
  notes: string;
  internal_notes: string;
  shipping_full_name: string;
  shipping_line1: string;
  shipping_city: string;
  shipping_state: string;
  shipping_state_code: string;
  shipping_pincode: string;
  shipping_country: string;
}

const defaultForm: OrderFormState = {
  guest_email: '',
  status: 'placed',
  payment_status: 'pending',
  payment_method: 'cod',
  subtotal: 0,
  discount_amount: 0,
  shipping_cost: 0,
  tax_amount: 0,
  grand_total: 0,
  currency: 'INR',
  coupon_code: '',
  notes: '',
  internal_notes: '',
  shipping_full_name: '',
  shipping_line1: '',
  shipping_city: '',
  shipping_state: '',
  shipping_state_code: '',
  shipping_pincode: '',
  shipping_country: 'India',
};

export const Orders: React.FC = () => {
  const [orders, setOrders] = useState<AdminOrderListRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingOrder, setEditingOrder] = useState<AdminOrderDetail | null>(null);
  const [formData, setFormData] = useState<OrderFormState>(defaultForm);
  const [saving, setSaving] = useState(false);
  const [orderToDelete, setOrderToDelete] = useState<AdminOrderListRow | null>(null);

  const [variantOptions, setVariantOptions] = useState<VariantOption[]>([]);
  const [variantSearch, setVariantSearch] = useState('');
  const [quickQtyByVariant, setQuickQtyByVariant] = useState<Record<string, number>>({});
  const [showVariantDropdown, setShowVariantDropdown] = useState(false);
  const [draftItems, setDraftItems] = useState<DraftOrderItem[]>([]);
  const [calcLoading, setCalcLoading] = useState(false);
  const [shipmentActionLoading, setShipmentActionLoading] = useState('');
  const [paymentActionLoading, setPaymentActionLoading] = useState('');
  const [calcBreakdown, setCalcBreakdown] = useState<any[]>([]);
  const [paymentTxns, setPaymentTxns] = useState<PaymentTxnView[]>([]);
  const [paymentTxnsLoading, setPaymentTxnsLoading] = useState(false);
  const [toasts, setToasts] = useState<UiToast[]>([]);
  const [customerSearch, setCustomerSearch] = useState('');
  const [customerOptions, setCustomerOptions] = useState<Customer[]>([]);
  const [showCustomerDropdown, setShowCustomerDropdown] = useState(false);
  const customerDropdownRef = useRef<HTMLDivElement | null>(null);

  const { formatCurrency } = useCurrency();

  const pushToast = (variant: UiToast['variant'], message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { id, variant, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 3200);
  };

  const loadOrders = async () => {
    try {
      setLoading(true);
      const response = await ordersService.listAdminOrders({
        search: searchTerm.trim() || undefined,
        status: statusFilter || undefined,
      });
      setOrders(extractRows(response) as AdminOrderListRow[]);
    } finally {
      setLoading(false);
    }
  };

  const loadVariants = async (search = '') => {
    const response = await inventoryService.listVariants({ search, active_only: true });
    setVariantOptions(extractRows(response) as VariantOption[]);
  };

  const loadCustomers = async (search = '') => {
    const response = await customerService.getAll({ search });
    setCustomerOptions(Array.isArray(response?.data) ? response.data : []);
  };

  const loadPaymentTransactions = async (orderId: string) => {
    try {
      setPaymentTxnsLoading(true);
      const response = await paymentsService.listAdminTransactions(orderId);
      const rows = Array.isArray(response?.data) ? (response.data as AdminPaymentTransaction[]) : [];
      setPaymentTxns(
        rows.map((row) => ({
          id: String(row.id || ''),
          provider: String(row.provider || ''),
          provider_ref: String(row.provider_ref || ''),
          status: String(row.status || ''),
          amount: Number(row.amount || row.total_amount || 0),
          currency: String(row.currency || 'INR'),
          created_at: String(row.created_at || ''),
          razorpay_payment_id: String(row.razorpay_payment_id || ''),
          razorpay_order_id: String(row.razorpay_order_id || ''),
        }))
      );
    } catch {
      setPaymentTxns([]);
    } finally {
      setPaymentTxnsLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isModalOpen || editingOrder) return;
    const term = variantSearch.trim();
    if (term.length < 2) {
      setVariantOptions([]);
      return;
    }
    loadVariants(term);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isModalOpen, editingOrder, variantSearch]);

  useEffect(() => {
    if (!isModalOpen) return;
    const term = customerSearch.trim();
    if (term.length < 2) {
      setCustomerOptions([]);
      return;
    }
    loadCustomers(term);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isModalOpen, editingOrder, customerSearch]);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (!customerDropdownRef.current) return;
      if (!customerDropdownRef.current.contains(event.target as Node)) {
        setShowCustomerDropdown(false);
      }
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const limitedVariantOptions = useMemo(() => variantOptions.slice(0, 8), [variantOptions]);
  const limitedCustomerOptions = useMemo(() => customerOptions.slice(0, 8), [customerOptions]);

  const filteredOrders = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return orders.filter((o) => {
      const matchesSearch = !q || [o.order_number, o.customer_name, o.customer_email].join(' ').toLowerCase().includes(q);
      const matchesStatus = !statusFilter || o.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [orders, searchTerm, statusFilter]);

  const columns = [
    {
      header: 'Order ID',
      accessorKey: 'order_number',
      className: 'font-bold',
      cell: (item: AdminOrderListRow) => <span>#{item.order_number}</span>,
    },
    {
      header: 'Customer',
      accessorKey: 'customer_name',
      cell: (item: AdminOrderListRow) => (
        <div className="flex flex-col">
          <span className="font-medium">{item.customer_name || 'Guest'}</span>
          <span className="text-xs text-muted-foreground">{item.customer_email || '-'}</span>
        </div>
      ),
    },
    {
      header: 'Date',
      accessorKey: 'created_at',
      className: 'text-muted-foreground',
      cell: (item: AdminOrderListRow) => new Date(item.created_at).toLocaleDateString(),
    },
    {
      header: 'Items',
      accessorKey: 'item_count',
      align: 'right' as const,
      cell: (item: AdminOrderListRow) => item.item_count || 0,
    },
    {
      header: 'Total',
      accessorKey: 'grand_total',
      align: 'right' as const,
      cell: (item: AdminOrderListRow) => (
        <span className="font-bold">{formatCurrency(Number(item.grand_total || 0))}</span>
      ),
    },
    {
      header: 'Status',
      accessorKey: 'status',
      align: 'right' as const,
      cell: (item: AdminOrderListRow) => <StatusBadge status={toTitle(item.status)} type="order" />,
    },
    {
      header: 'Invoice',
      accessorKey: 'invoice_url',
      align: 'right' as const,
      cell: (item: AdminOrderListRow) => (
        <Button
          size="sm"
          variant="outline"
          className="h-8 rounded-lg"
          onClick={(event) => {
            event.stopPropagation();
            void handleAdminInvoiceDownload(item.id, item.invoice_url);
          }}
        >
          <FileDown className="mr-1 h-3.5 w-3.5" />
          Invoice
        </Button>
      ),
    },
  ];

  const openCreate = () => {
    setEditingOrder(null);
    setFormData(defaultForm);
    setDraftItems([]);
    setCalcBreakdown([]);
    setQuickQtyByVariant({});
    setCustomerSearch('');
    setCustomerOptions([]);
    setShowCustomerDropdown(false);
    setPaymentTxns([]);
    setIsModalOpen(true);
  };

  const openEdit = async (order: AdminOrderListRow) => {
    try {
      const response = await ordersService.getAdminOrder(order.id);
      const detail = response?.data as AdminOrderDetail;
      setEditingOrder(detail);
      setFormData({
        guest_email: detail.customer_email || '',
        status: detail.status || 'placed',
        payment_status: detail.payment_status || 'pending',
        payment_method: detail.payment_method || 'cod',
        subtotal: Number(detail.subtotal || 0),
        discount_amount: Number(detail.discount_amount || 0),
        shipping_cost: Number(detail.shipping_cost || 0),
        tax_amount: Number(detail.tax_amount || 0),
        grand_total: Number(detail.grand_total || 0),
        currency: detail.currency || 'INR',
        coupon_code: (detail as any).coupon_code || '',
        notes: detail.notes || '',
        internal_notes: detail.internal_notes || '',
        shipping_full_name: String((detail.shipping_address || {}).full_name || ''),
        shipping_line1: String((detail.shipping_address || {}).line1 || ''),
        shipping_city: String((detail.shipping_address || {}).city || ''),
        shipping_state: String((detail.shipping_address || {}).state || ''),
        shipping_state_code: String((detail.shipping_address || {}).state_code || ''),
        shipping_pincode: String((detail.shipping_address || {}).pincode || ''),
        shipping_country: String((detail.shipping_address || {}).country || 'India'),
      });
      setCustomerSearch(detail.customer_email || '');
      setCustomerOptions([]);
      setShowCustomerDropdown(false);
      await loadPaymentTransactions(detail.id);
      setIsModalOpen(true);
    } catch (error: any) {
      alert(error?.response?.data?.message || 'Failed to load order details.');
    }
  };

  const runShipmentAction = async (action: 'create' | 'pickup' | 'refresh' | 'cancel') => {
    if (!editingOrder) return;
    try {
      setShipmentActionLoading(action);
      if (action === 'create') {
        await shippingService.createShipmentForOrder(editingOrder.id, true);
      } else if (action === 'pickup' && editingOrder.shipment?.id) {
        await shippingService.requestPickup(editingOrder.shipment.id);
      } else if (action === 'refresh' && editingOrder.shipment?.id) {
        await shippingService.refreshTracking(editingOrder.shipment.id);
      } else if (action === 'cancel' && editingOrder.shipment?.id) {
        await shippingService.cancelShipment(editingOrder.shipment.id);
      }
      await openEdit(editingOrder);
    } catch (error: any) {
      alert(error?.response?.data?.message || 'Shipment action failed.');
    } finally {
      setShipmentActionLoading('');
    }
  };

  const reconcilePayment = async () => {
    if (!editingOrder) return;
    try {
      setPaymentActionLoading('reconcile');
      const response = await paymentsService.reconcileAdminOrder(editingOrder.id);
      const reconciledStatus = String(response?.data?.payment_status || '').trim();
      if (reconciledStatus) {
        setFormData((prev) => ({ ...prev, payment_status: reconciledStatus }));
      }
      await loadPaymentTransactions(editingOrder.id);
      await openEdit(editingOrder);
      pushToast('success', response?.message || 'Payment status reconciled.');
    } catch (error: any) {
      pushToast('error', error?.response?.data?.message || 'Failed to reconcile payment.');
    } finally {
      setPaymentActionLoading('');
    }
  };

  const markOrderPaidNow = async () => {
    if (!editingOrder) return;
    try {
      setPaymentActionLoading('mark-paid');
      const candidateRef = paymentTxns.find((txn) => txn.status === 'success')?.provider_ref || '';
      await ordersService.markAdminOrderPaid(editingOrder.id, {
        payment_method: formData.payment_method || 'razorpay',
        payment_reference: candidateRef || undefined,
      });
      setFormData((prev) => ({ ...prev, payment_status: 'paid', status: prev.status === 'draft' ? 'paid' : prev.status }));
      await loadPaymentTransactions(editingOrder.id);
      await openEdit(editingOrder);
      pushToast('success', 'Order marked as paid.');
    } catch (error: any) {
      pushToast('error', error?.response?.data?.message || 'Failed to mark order as paid.');
    } finally {
      setPaymentActionLoading('');
    }
  };

  const handleAdminInvoiceDownload = async (orderId: string, invoiceUrl?: string) => {
    try {
      await ordersService.downloadInvoice(orderId, invoiceUrl);
    } catch {
      await ordersService.regenerateInvoice(orderId);
      await ordersService.downloadInvoice(orderId);
    }
  };

  const addDraftItem = (variantId: string, requestedQty?: number) => {
    if (!variantId) return;
    const selected = variantOptions.find((v) => v.id === variantId);
    if (!selected) return;
    const qty = Math.max(1, Number(requestedQty || 1));

    setDraftItems((prev) => {
      const existing = prev.find((i) => i.variant_id === selected.id);
      if (existing) {
        return prev.map((i) => i.variant_id === selected.id ? { ...i, quantity: i.quantity + qty } : i);
      }
      return [
        ...prev,
        {
          variant_id: selected.id,
          sku: selected.sku,
          product_name: selected.product_name,
          variant_name: selected.name || selected.sku,
          unit_price: Number(selected.price || 0),
          quantity: qty,
        },
      ];
    });
  };

  const removeDraftItem = (variantId: string) => {
    setDraftItems((prev) => prev.filter((i) => i.variant_id !== variantId));
  };

  const selectCustomer = (customer: Customer) => {
    const addresses = Array.isArray(customer.addresses) ? customer.addresses : [];
    const shipping =
      addresses.find((a: AddressData) => a.address_type === 'shipping' && a.is_default) ||
      addresses.find((a: AddressData) => a.address_type === 'shipping') ||
      addresses.find((a: AddressData) => a.is_default) ||
      addresses[0];
    setFormData((prev) => ({
      ...prev,
      guest_email: customer.email || prev.guest_email,
      shipping_full_name: shipping?.full_name || `${customer.first_name || ''} ${customer.last_name || ''}`.trim() || prev.shipping_full_name,
      shipping_line1: shipping?.line1 || prev.shipping_line1,
      shipping_city: shipping?.city || prev.shipping_city,
      shipping_state: shipping?.state || prev.shipping_state,
      shipping_pincode: shipping?.postal_code || prev.shipping_pincode,
      shipping_country: shipping?.country || prev.shipping_country,
    }));
    setCustomerSearch('');
    setShowCustomerDropdown(false);
  };

  const updateDraftItemQty = (variantId: string, quantity: number) => {
    const safeQty = Math.max(1, Number(quantity || 1));
    setDraftItems((prev) => prev.map((i) => i.variant_id === variantId ? { ...i, quantity: safeQty } : i));
  };

  const calculateTotals = async () => {
    if (draftItems.length === 0) {
      alert('Add at least one item to calculate totals.');
      return;
    }

    try {
      setCalcLoading(true);
      const response = await ordersService.calculateAdminOrder({
        payment_method: formData.payment_method,
        coupon_code: formData.coupon_code,
        shipping_address: {
          full_name: formData.shipping_full_name,
          line1: formData.shipping_line1,
          city: formData.shipping_city,
          state: formData.shipping_state,
          state_code: formData.shipping_state_code,
          pincode: formData.shipping_pincode,
          country: formData.shipping_country,
        },
        items: draftItems.map((i) => ({ variant_id: i.variant_id, quantity: i.quantity })),
      });

      const data = response?.data || {};
      setFormData((prev) => ({
        ...prev,
        subtotal: Number(data.subtotal || 0),
        discount_amount: Number(data.discount_amount || 0),
        shipping_cost: Number(data.shipping_cost || 0),
        tax_amount: Number(data.tax_amount || 0),
        grand_total: Number(data.grand_total || 0),
      }));
      setCalcBreakdown(Array.isArray(data.breakdown) ? data.breakdown : []);
    } catch (error: any) {
      alert(error?.response?.data?.message || 'Failed to calculate totals.');
    } finally {
      setCalcLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      if (!editingOrder) {
        if (draftItems.length === 0) {
          alert('Please add at least one product item.');
          return;
        }
        await ordersService.createAdminOrder({
          guest_email: formData.guest_email,
          status: formData.status,
          payment_status: formData.payment_status,
          payment_method: formData.payment_method,
          coupon_code: formData.coupon_code,
          notes: formData.notes,
          internal_notes: formData.internal_notes,
          shipping_address: {
            full_name: formData.shipping_full_name,
            line1: formData.shipping_line1,
            city: formData.shipping_city,
            state: formData.shipping_state,
            state_code: formData.shipping_state_code,
            pincode: formData.shipping_pincode,
            country: formData.shipping_country,
          },
          billing_address: {
            full_name: formData.shipping_full_name,
            line1: formData.shipping_line1,
            city: formData.shipping_city,
            state: formData.shipping_state,
            state_code: formData.shipping_state_code,
            pincode: formData.shipping_pincode,
            country: formData.shipping_country,
          },
          items: draftItems.map((i) => ({ variant_id: i.variant_id, quantity: i.quantity })),
        });
      } else {
        await ordersService.updateAdminOrder(editingOrder.id, {
          payment_status: formData.payment_status,
          payment_method: formData.payment_method,
          shipping_address: {
            full_name: formData.shipping_full_name,
            line1: formData.shipping_line1,
            city: formData.shipping_city,
            state: formData.shipping_state,
            state_code: formData.shipping_state_code,
            pincode: formData.shipping_pincode,
            country: formData.shipping_country,
          },
          billing_address: {
            full_name: formData.shipping_full_name,
            line1: formData.shipping_line1,
            city: formData.shipping_city,
            state: formData.shipping_state,
            state_code: formData.shipping_state_code,
            pincode: formData.shipping_pincode,
            country: formData.shipping_country,
          },
          subtotal: formData.subtotal,
          discount_amount: formData.discount_amount,
          shipping_cost: formData.shipping_cost,
          tax_amount: formData.tax_amount,
          grand_total: formData.grand_total,
          currency: formData.currency,
          notes: formData.notes,
          internal_notes: formData.internal_notes,
        });
        if (formData.status !== editingOrder.status) {
          await ordersService.transitionOrder(editingOrder.id, {
            new_status: formData.status,
            notes: 'Updated from admin Orders page.',
          });
        }
      }
      setIsModalOpen(false);
      await loadOrders();
    } catch (error: any) {
      const msg = error?.response?.data?.message || 'Failed to save order.';
      alert(msg);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!orderToDelete) return;
    try {
      await ordersService.deleteAdminOrder(orderToDelete.id);
      setOrderToDelete(null);
      await loadOrders();
    } catch (error: any) {
      alert(error?.response?.data?.message || 'Failed to delete order.');
    }
  };

  const actions = (item: AdminOrderListRow) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[180px]">
        <DropdownMenuItem onClick={() => openEdit(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Eye size={14} /> View / Edit
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => {
            void handleAdminInvoiceDownload(item.id, item.invoice_url);
          }}
          className="flex items-center gap-2 cursor-pointer text-xs"
        >
          <FileDown size={14} /> Download Invoice
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={async () => {
            await ordersService.regenerateInvoice(item.id);
            await loadOrders();
          }}
          className="flex items-center gap-2 cursor-pointer text-xs"
        >
          <RotateCw size={14} /> Regenerate Invoice
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={async () => {
            try {
              const response = await ordersService.sendOrderConfirmationEmail(item.id);
              pushToast('success', response?.message || 'Order confirmation email queued.');
            } catch (error: any) {
              const message = error?.response?.data?.message || 'Failed to send order confirmation email.';
              pushToast('error', message);
            }
          }}
          className="flex items-center gap-2 cursor-pointer text-xs"
        >
          <Mail size={14} /> Send Confirmation Email
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setOrderToDelete(item)}
          className="flex items-center gap-2 cursor-pointer text-xs text-destructive focus:text-destructive"
        >
          <Trash2 size={14} /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Orders</h1>
          <p className="text-xs text-muted-foreground mt-1">Manage and track customer orders.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={loadOrders} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm border-border/60 bg-white">
            <RefreshCw size={16} /> Refresh
          </Button>
          <Button onClick={openCreate} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm">
            <Plus size={16} /> Add Order
          </Button>
        </div>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input
            placeholder="Search by Order ID, Customer Name or Email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-10 shadow-none border-border/60 bg-muted/20"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="h-10 px-4 gap-2 text-muted-foreground border-border/60">
            <Filter size={16} /> Filters
          </Button>
          <select
            className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Status</option>
            {statusOptions.map((s) => (
              <option key={s} value={s}>{toTitle(s)}</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">
          Loading orders...
        </div>
      ) : (
        <DataTable data={filteredOrders} columns={columns} actions={actions} onRowClick={(item) => openEdit(item as AdminOrderListRow)} />
      )}

      <Modal open={isModalOpen} onOpenChange={setIsModalOpen}>
        <ModalContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <ModalHeader>
            <ModalTitle>{editingOrder ? `Edit Order #${editingOrder.order_number}` : 'Create Order'}</ModalTitle>
          </ModalHeader>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4">
            <div className="grid gap-2 md:col-span-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Customer Email (guest/manual)</label>
              <div ref={customerDropdownRef} className="space-y-2 relative">
                <Input
                  value={formData.guest_email}
                  onChange={(e) => {
                    const value = e.target.value;
                    setFormData({ ...formData, guest_email: value });
                    setCustomerSearch(value);
                    setShowCustomerDropdown(true);
                  }}
                  onFocus={() => {
                    if (formData.guest_email.trim().length >= 2) {
                      setCustomerSearch(formData.guest_email);
                      setShowCustomerDropdown(true);
                    }
                  }}
                />
                {showCustomerDropdown && customerSearch.trim().length >= 2 ? (
                  <div className="absolute z-30 w-full max-h-44 overflow-y-auto rounded-lg border border-border/70 bg-white shadow-sm">
                    {limitedCustomerOptions.length === 0 ? (
                      <div className="px-3 py-4 text-xs text-muted-foreground">No matching customers found.</div>
                    ) : (
                      limitedCustomerOptions.map((c) => (
                        <div key={c.id} className="flex items-center justify-between gap-2 px-3 py-2 text-xs border-b border-border/50 last:border-b-0">
                          <div className="min-w-0">
                            <div className="font-semibold truncate">{`${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Customer'}</div>
                            <div className="text-muted-foreground truncate">{c.email}</div>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-[11px] border-primary/50 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
                            onClick={() => selectCustomer(c)}
                          >
                            Select
                          </Button>
                        </div>
                      ))
                    )}
                  </div>
                ) : null}
                {formData.guest_email.trim().length > 0 && formData.guest_email.trim().length < 2 ? (
                  <p className="text-[11px] text-muted-foreground px-1">Type at least 2 characters to search customers.</p>
                ) : null}
              </div>
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Status</label>
              <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })}>
                {(editingOrder ? statusOptions : statusOptions.filter((s) => s !== 'draft')).map((s) => <option key={s} value={s}>{toTitle(s)}</option>)}
              </select>
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Payment Method</label>
              <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={formData.payment_method} onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}>
                {paymentMethodOptions.map((s) => <option key={s} value={s}>{toTitle(s)}</option>)}
              </select>
            </div>

            {!editingOrder ? (
              <>
                <div className="md:col-span-2 rounded-xl border border-border bg-muted/20 p-3 space-y-3">
                  <p className="text-xs font-bold uppercase text-muted-foreground">Add Products</p>
                  <div className="grid grid-cols-1 gap-2">
                    <Input
                      placeholder="Search variant by SKU or product"
                      value={variantSearch}
                      onChange={(e) => {
                        setVariantSearch(e.target.value);
                        setShowVariantDropdown(true);
                      }}
                      onFocus={() => {
                        if (variantSearch.trim().length >= 2) {
                          setShowVariantDropdown(true);
                        }
                      }}
                    />
                    {showVariantDropdown && variantSearch.trim().length >= 2 ? (
                      <div className="max-h-48 overflow-y-auto rounded-lg border border-border/70 bg-white shadow-sm">
                        {limitedVariantOptions.length === 0 ? (
                          <div className="px-3 py-4 text-xs text-muted-foreground">No matching products found.</div>
                        ) : (
                          limitedVariantOptions.map((v) => {
                          const quickQty = Math.max(1, Number(quickQtyByVariant[v.id] || 1));
                          return (
                            <div key={v.id} className="flex items-center justify-between gap-2 px-3 py-2 text-xs border-b border-border/50 last:border-b-0">
                              <div className="min-w-0">
                                <div className="font-semibold truncate">{v.product_name}</div>
                                <div className="text-muted-foreground truncate">{v.sku} • {formatCurrency(Number(v.price || 0))}</div>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <Input
                                  type="number"
                                  min={1}
                                  className="h-8 w-16"
                                  value={quickQty}
                                  onChange={(e) => setQuickQtyByVariant((prev) => ({ ...prev, [v.id]: Math.max(1, Number(e.target.value || 1)) }))}
                                />
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2 text-[11px] border-primary/50 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
                                  onClick={() => {
                                    addDraftItem(v.id, quickQty);
                                    setVariantSearch('');
                                    setShowVariantDropdown(false);
                                  }}
                                >
                                  Add
                                </Button>
                              </div>
                            </div>
                          );
                          })
                        )}
                      </div>
                    ) : null}
                    {variantSearch.trim().length > 0 && variantSearch.trim().length < 2 ? (
                      <p className="text-[11px] text-muted-foreground px-1">Type at least 2 characters to search.</p>
                    ) : null}
                  </div>

                  <div className="space-y-2">
                    {draftItems.length === 0 ? <p className="text-xs text-muted-foreground">No items added yet.</p> : null}
                    {draftItems.map((i) => (
                      <div key={i.variant_id} className="flex items-center justify-between text-xs rounded-lg border border-border/70 bg-white p-2">
                        <div>
                          <div className="font-semibold">{i.product_name} ({i.sku})</div>
                          <div className="text-muted-foreground">Unit: {formatCurrency(i.unit_price)}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            min={1}
                            className="h-8 w-16"
                            value={i.quantity}
                            onChange={(e) => updateDraftItemQty(i.variant_id, Number(e.target.value || 1))}
                          />
                          <Button variant="ghost" size="sm" className="text-destructive" onClick={() => removeDraftItem(i.variant_id)}>Remove</Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-2 md:col-span-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Coupon Code</label>
                  <Input value={formData.coupon_code} onChange={(e) => setFormData({ ...formData, coupon_code: e.target.value })} placeholder="Optional" />
                </div>

                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Shipping Name</label>
                  <Input value={formData.shipping_full_name} onChange={(e) => setFormData({ ...formData, shipping_full_name: e.target.value })} />
                </div>
                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Address Line 1</label>
                  <Input value={formData.shipping_line1} onChange={(e) => setFormData({ ...formData, shipping_line1: e.target.value })} />
                </div>
                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">City</label>
                  <Input value={formData.shipping_city} onChange={(e) => setFormData({ ...formData, shipping_city: e.target.value })} />
                </div>
                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">State</label>
                  <Input value={formData.shipping_state} onChange={(e) => setFormData({ ...formData, shipping_state: e.target.value })} />
                </div>
                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">State Code</label>
                  <Input value={formData.shipping_state_code} onChange={(e) => setFormData({ ...formData, shipping_state_code: e.target.value })} />
                </div>
                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Pincode</label>
                  <Input value={formData.shipping_pincode} onChange={(e) => setFormData({ ...formData, shipping_pincode: e.target.value })} />
                </div>
              </>
            ) : (
              <>
                <div className="grid gap-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Payment Status</label>
                  <select className="h-10 rounded-md border border-border/60 bg-white px-3 text-sm" value={formData.payment_status} onChange={(e) => setFormData({ ...formData, payment_status: e.target.value })}>
                    {paymentStatusOptions.map((s) => <option key={s} value={s}>{toTitle(s)}</option>)}
                  </select>
                </div>
              </>
            )}

            {editingOrder ? (
              <div className="md:col-span-2 rounded-xl border border-border bg-white p-3 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-bold uppercase text-muted-foreground">Payment Timeline</p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void loadPaymentTransactions(editingOrder.id)}
                      disabled={paymentTxnsLoading || paymentActionLoading.length > 0}
                    >
                      {paymentTxnsLoading ? 'Refreshing...' : 'Refresh Payment Logs'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={reconcilePayment}
                      disabled={paymentActionLoading.length > 0}
                    >
                      {paymentActionLoading === 'reconcile' ? 'Reconciling...' : 'Reconcile with Gateway'}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      onClick={markOrderPaidNow}
                      disabled={paymentActionLoading.length > 0 || formData.payment_status === 'paid'}
                    >
                      {paymentActionLoading === 'mark-paid' ? 'Updating...' : 'Mark Paid Manually'}
                    </Button>
                  </div>
                </div>

                {paymentTxns.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No payment transactions found for this order yet.</p>
                ) : (
                  <div className="space-y-2">
                    {paymentTxns.slice(0, 5).map((txn) => (
                      <div key={txn.id} className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-semibold uppercase">{txn.provider}</span>
                          <StatusBadge status={toTitle(txn.status)} type="generic" />
                        </div>
                        <div className="mt-1 text-muted-foreground">
                          Amount: {formatCurrency(Number(txn.amount || 0))} {txn.currency}
                        </div>
                        <div className="text-muted-foreground break-all">
                          Ref: {txn.razorpay_payment_id || txn.provider_ref || txn.razorpay_order_id || '-'}
                        </div>
                        <div className="text-muted-foreground">
                          {txn.created_at ? new Date(txn.created_at).toLocaleString() : '-'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}

            <div className="md:col-span-2 rounded-xl border border-border bg-muted/20 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold uppercase text-muted-foreground">Totals</p>
                {!editingOrder ? (
                  <Button type="button" variant="outline" size="sm" onClick={calculateTotals} disabled={calcLoading}>
                    {calcLoading ? 'Calculating...' : 'Calculate Totals'}
                  </Button>
                ) : null}
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>Subtotal</div><div className="text-right font-semibold">{formatCurrency(formData.subtotal)}</div>
                <div>Discount</div><div className="text-right font-semibold">{formatCurrency(formData.discount_amount)}</div>
                <div>Shipping</div><div className="text-right font-semibold">{formatCurrency(formData.shipping_cost)}</div>
                <div>Tax</div><div className="text-right font-semibold">{formatCurrency(formData.tax_amount)}</div>
                <div className="font-bold">Grand Total</div><div className="text-right font-bold">{formatCurrency(formData.grand_total)}</div>
              </div>
              {calcBreakdown.length > 0 ? (
                <div className="mt-2 border-t border-border pt-2 space-y-1">
                  {calcBreakdown.map((line, idx) => (
                    <div key={`${line.name}-${idx}`} className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>{line.name}</span>
                      <span>{formatCurrency(Number(line.amount || 0))}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="grid gap-2 md:col-span-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Notes</label>
              <Input value={formData.notes} onChange={(e) => setFormData({ ...formData, notes: e.target.value })} />
            </div>

            {editingOrder?.items?.length ? (
              <div className="md:col-span-2 rounded-xl border border-border bg-muted/20 p-3 space-y-2">
                <p className="text-xs font-bold uppercase text-muted-foreground">Order Items ({editingOrder.items.length})</p>
                {editingOrder.items.map((item) => (
                  <div key={item.id} className="flex items-center justify-between gap-3 text-xs border-b border-border/60 pb-2 last:border-0 last:pb-0">
                    <div className="flex items-center gap-3">
                      <img
                        src={item.product_image || 'https://placehold.co/80x80/f3f4f6/6b7280?text=Product'}
                        alt={item.product_name}
                        className="h-10 w-10 rounded-md border border-border/70 object-cover"
                      />
                      <span>{item.product_name} ({item.sku}) × {item.quantity}</span>
                    </div>
                    <span className="font-semibold">{formatCurrency(Number(item.line_total || 0))}</span>
                  </div>
                ))}
              </div>
            ) : null}

            {editingOrder ? (
              <div className="md:col-span-2 rounded-xl border border-border bg-white p-3 space-y-2">
                <p className="text-xs font-bold uppercase text-muted-foreground">Delivery Address</p>
                <div className="text-sm leading-relaxed text-foreground">
                  <p className="font-semibold">{String(editingOrder.shipping_address?.full_name || editingOrder.customer_name || 'Customer')}</p>
                  <p>{String(editingOrder.shipping_address?.line1 || '-')}</p>
                  {editingOrder.shipping_address?.line2 ? <p>{String(editingOrder.shipping_address.line2)}</p> : null}
                  <p>
                    {String(editingOrder.shipping_address?.city || '')}
                    {editingOrder.shipping_address?.state ? `, ${String(editingOrder.shipping_address.state)}` : ''}
                    {editingOrder.shipping_address?.pincode ? ` - ${String(editingOrder.shipping_address.pincode)}` : ''}
                  </p>
                  <p>{String(editingOrder.shipping_address?.country || 'India')}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Email: {editingOrder.customer_email || editingOrder.guest_email || '-'}</p>
                  <p className="text-xs text-muted-foreground">Contact: {String(editingOrder.shipping_address?.phone || '-')}</p>
                </div>
              </div>
            ) : null}

            {editingOrder ? (
              <div className="md:col-span-2 rounded-xl border border-border bg-white p-3 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-bold uppercase text-muted-foreground">Shipment</p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => runShipmentAction('create')}
                      disabled={shipmentActionLoading === 'create'}
                    >
                      {shipmentActionLoading === 'create' ? 'Queuing...' : 'Retry Shipment Sync'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => runShipmentAction('refresh')}
                      disabled={!editingOrder.shipment?.id || shipmentActionLoading === 'refresh'}
                    >
                      {shipmentActionLoading === 'refresh' ? 'Queuing...' : 'Refresh Tracking'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => runShipmentAction('pickup')}
                      disabled={!editingOrder.shipment?.id || shipmentActionLoading === 'pickup'}
                    >
                      {shipmentActionLoading === 'pickup' ? 'Queuing...' : 'Request Pickup'}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => runShipmentAction('cancel')}
                      disabled={!editingOrder.shipment?.id || shipmentActionLoading === 'cancel'}
                      className="text-destructive border-destructive/40 hover:bg-destructive hover:text-destructive-foreground"
                    >
                      {shipmentActionLoading === 'cancel' ? 'Cancelling...' : 'Cancel Shipment'}
                    </Button>
                  </div>
                </div>

                {!editingOrder.shipment ? (
                  <p className="text-xs text-muted-foreground">No shipment has been created yet.</p>
                ) : (
                  <div className="space-y-2 text-xs">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div className="rounded-lg border border-border/70 p-2">
                        <div className="text-muted-foreground">Provider</div>
                        <div className="font-semibold">{toTitle(editingOrder.shipment.provider || '-')}</div>
                      </div>
                      <div className="rounded-lg border border-border/70 p-2">
                        <div className="text-muted-foreground">Status</div>
                        <div className="font-semibold">{toTitle(editingOrder.shipment.status || '-')}</div>
                      </div>
                      <div className="rounded-lg border border-border/70 p-2">
                        <div className="text-muted-foreground">AWB</div>
                        <div className="font-semibold">{editingOrder.shipment.awb_code || '-'}</div>
                      </div>
                      <div className="rounded-lg border border-border/70 p-2">
                        <div className="text-muted-foreground">Courier</div>
                        <div className="font-semibold">{editingOrder.shipment.courier_name || '-'}</div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      {editingOrder.shipment.tracking_url ? (
                        <a href={editingOrder.shipment.tracking_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          Tracking Link
                        </a>
                      ) : null}
                    {editingOrder.shipment.label_url ? (
                        <a href={editingOrder.shipment.label_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          Label
                        </a>
                      ) : null}
                      {editingOrder.shipment.manifest_url ? (
                        <a href={editingOrder.shipment.manifest_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          Manifest
                        </a>
                      ) : null}
                    </div>
                    {(editingOrder.shipment.events || []).length ? (
                      <div className="rounded-lg border border-border/70 p-2 space-y-2">
                        <div className="text-muted-foreground font-semibold">Shipment History</div>
                        {(editingOrder.shipment.events || []).slice(0, 8).map((event) => (
                          <div key={event.id} className="flex items-center justify-between gap-2">
                            <div>
                              <div className="font-medium">{toTitle(event.internal_status || event.provider_status || 'updated')}</div>
                              <div className="text-muted-foreground">
                                {toTitle(event.source || 'system')} • {new Date(event.created_at).toLocaleString()}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {editingOrder.shipment.error_message ? (
                      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-2 text-destructive">
                        {editingOrder.shipment.error_message}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            ) : null}

            {editingOrder ? (
              <div className="md:col-span-2 rounded-xl border border-border bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-bold uppercase text-muted-foreground">Invoice</p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void handleAdminInvoiceDownload(editingOrder.id, editingOrder.invoice_url);
                      }}
                    >
                      <FileDown className="mr-1 h-3.5 w-3.5" /> Download
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void ordersService.downloadShippingLabel(editingOrder.id);
                      }}
                    >
                      <FileDown className="mr-1 h-3.5 w-3.5" /> Shipping Label
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void ordersService.printShippingLabel(editingOrder.id);
                      }}
                    >
                      <Printer className="mr-1 h-3.5 w-3.5" /> Print Label
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        await ordersService.regenerateInvoice(editingOrder.id);
                        await openEdit(editingOrder);
                      }}
                    >
                      <RotateCw className="mr-1 h-3.5 w-3.5" /> Regenerate
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <ModalFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)} disabled={saving}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>{saving ? 'Saving...' : 'Save Order'}</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <ConfirmDialog
        open={Boolean(orderToDelete)}
        onOpenChange={(open) => {
          if (!open) setOrderToDelete(null);
        }}
        title="Delete Order"
        description="This order will be permanently deleted. Paid and fulfilled orders cannot be deleted."
        confirmLabel="Delete Order"
        variant="destructive"
        onConfirm={confirmDelete}
      />

      <div className="pointer-events-none fixed right-5 top-5 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={[
              'rounded-xl border bg-white px-4 py-3 text-sm shadow-lg',
              toast.variant === 'success' ? 'border-emerald-300 text-emerald-700' : '',
              toast.variant === 'error' ? 'border-destructive/40 text-destructive' : '',
            ].join(' ')}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
};
