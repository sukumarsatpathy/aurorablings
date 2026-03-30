import React, { useEffect, useMemo, useState } from 'react';
import { Plus, Search, MoreHorizontal, Edit, Trash2, Power } from 'lucide-react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu';
import {
  Modal,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from '@/components/ui/Modal';
import couponService from '@/services/api/coupons';
import type { Coupon, CouponType, CouponWriteData } from '@/types/coupon';

type CouponFormState = {
  code: string;
  type: CouponType;
  value: string;
  max_discount: string;
  min_order_value: string;
  usage_limit: string;
  per_user_limit: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
};

const DEFAULT_FORM: CouponFormState = {
  code: '',
  type: 'percentage',
  value: '',
  max_discount: '',
  min_order_value: '0',
  usage_limit: '',
  per_user_limit: '',
  start_date: '',
  end_date: '',
  is_active: true,
};

const formatCurrency = (value: string | null | number) => {
  const numericValue = Number(value ?? 0);
  if (Number.isNaN(numericValue)) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(numericValue);
};

const toDateTimeLocalValue = (value: string | null | undefined) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const timezoneOffsetMs = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - timezoneOffsetMs).toISOString().slice(0, 16);
};

const toIsoString = (value: string) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toISOString();
};

export const Coupons: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingCoupon, setEditingCoupon] = useState<Coupon | null>(null);
  const [couponToDelete, setCouponToDelete] = useState<Coupon | null>(null);
  const [formData, setFormData] = useState<CouponFormState>(DEFAULT_FORM);

  const fetchCoupons = async () => {
    try {
      setLoading(true);
      const response = await couponService.getAll();
      setCoupons(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to fetch coupons:', error);
      setCoupons([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCoupons();
  }, []);

  const filteredCoupons = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return coupons.filter((coupon) => {
      const searchMatch = q
        ? `${coupon.code} ${coupon.type}`.toLowerCase().includes(q)
        : true;
      const activeMatch =
        activeFilter === 'all'
          ? true
          : activeFilter === 'active'
            ? coupon.is_active
            : !coupon.is_active;
      return searchMatch && activeMatch;
    });
  }, [activeFilter, coupons, searchTerm]);

  const summary = useMemo(() => {
    const active = coupons.filter((coupon) => coupon.is_active).length;
    const inactive = coupons.length - active;
    return { total: coupons.length, active, inactive };
  }, [coupons]);

  const openAddModal = () => {
    setEditingCoupon(null);
    setFormData(DEFAULT_FORM);
    setIsModalOpen(true);
  };

  const openEditModal = (coupon: Coupon) => {
    setEditingCoupon(coupon);
    setFormData({
      code: coupon.code,
      type: coupon.type,
      value: String(coupon.value ?? ''),
      max_discount: coupon.max_discount ? String(coupon.max_discount) : '',
      min_order_value: String(coupon.min_order_value ?? '0'),
      usage_limit: coupon.usage_limit !== null ? String(coupon.usage_limit) : '',
      per_user_limit: coupon.per_user_limit !== null ? String(coupon.per_user_limit) : '',
      start_date: toDateTimeLocalValue(coupon.start_date),
      end_date: toDateTimeLocalValue(coupon.end_date),
      is_active: coupon.is_active,
    });
    setIsModalOpen(true);
  };

  const openDeleteModal = (coupon: Coupon) => {
    setCouponToDelete(coupon);
    setIsDeleteModalOpen(true);
  };

  const handleDelete = async () => {
    if (!couponToDelete) return;
    try {
      await couponService.delete(couponToDelete.id);
      setIsDeleteModalOpen(false);
      setCouponToDelete(null);
      await fetchCoupons();
    } catch (error) {
      console.error('Failed to delete coupon:', error);
      alert('Failed to delete coupon.');
    }
  };

  const handleQuickToggle = async (coupon: Coupon) => {
    try {
      await couponService.update(coupon.id, { is_active: !coupon.is_active });
      await fetchCoupons();
    } catch (error) {
      console.error('Failed to update coupon status:', error);
      alert('Failed to update coupon status.');
    }
  };

  const handleSave = async () => {
    if (!formData.code.trim()) {
      alert('Coupon code is required.');
      return;
    }

    const value = Number(formData.value);
    if (!Number.isFinite(value) || value <= 0) {
      alert('Value must be greater than 0.');
      return;
    }

    if (formData.type === 'percentage' && value > 100) {
      alert('Percentage coupon cannot exceed 100.');
      return;
    }

    const startDateIso = toIsoString(formData.start_date);
    const endDateIso = toIsoString(formData.end_date);
    if (!startDateIso || !endDateIso) {
      alert('Start date and end date are required.');
      return;
    }
    if (new Date(endDateIso) <= new Date(startDateIso)) {
      alert('End date must be after start date.');
      return;
    }

    const payload: CouponWriteData = {
      code: formData.code.trim().toUpperCase(),
      type: formData.type,
      value,
      max_discount: formData.max_discount.trim() ? Number(formData.max_discount) : null,
      min_order_value: formData.min_order_value.trim() ? Number(formData.min_order_value) : 0,
      usage_limit: formData.usage_limit.trim() ? Number(formData.usage_limit) : null,
      per_user_limit: formData.per_user_limit.trim() ? Number(formData.per_user_limit) : null,
      start_date: startDateIso,
      end_date: endDateIso,
      is_active: formData.is_active,
    };

    try {
      if (editingCoupon) {
        await couponService.update(editingCoupon.id, payload);
      } else {
        await couponService.create(payload);
      }
      setIsModalOpen(false);
      await fetchCoupons();
    } catch (error) {
      console.error('Failed to save coupon:', error);
      alert('Failed to save coupon.');
    }
  };

  const columns = [
    { header: 'Code', accessorKey: 'code', cell: (item: Coupon) => <span className="font-bold">{item.code}</span> },
    {
      header: 'Type',
      accessorKey: 'type',
      cell: (item: Coupon) => (
        <Badge variant="outline" className="text-[10px] uppercase">
          {item.type}
        </Badge>
      ),
    },
    {
      header: 'Value',
      accessorKey: 'value',
      cell: (item: Coupon) =>
        item.type === 'percentage' ? `${item.value}%` : formatCurrency(item.value),
      align: 'right' as const,
    },
    {
      header: 'Min Order',
      accessorKey: 'min_order_value',
      cell: (item: Coupon) => formatCurrency(item.min_order_value),
      align: 'right' as const,
    },
    {
      header: 'Max Discount',
      accessorKey: 'max_discount',
      cell: (item: Coupon) => (item.max_discount ? formatCurrency(item.max_discount) : 'No cap'),
      align: 'right' as const,
    },
    {
      header: 'Limits',
      accessorKey: 'usage_limit',
      cell: (item: Coupon) => (
        <div className="text-xs text-right">
          <div>Total: {item.usage_limit ?? '∞'}</div>
          <div className="text-muted-foreground">Per user: {item.per_user_limit ?? '∞'}</div>
        </div>
      ),
      align: 'right' as const,
    },
    {
      header: 'Status',
      accessorKey: 'is_active',
      cell: (item: Coupon) => <StatusBadge status={item.is_active ? 'Active' : 'Inactive'} />,
      align: 'center' as const,
    },
  ];

  const actions = (item: Coupon) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[190px]">
        <DropdownMenuItem onClick={() => openEditModal(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Edit size={14} /> Edit Coupon
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleQuickToggle(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Power size={14} /> {item.is_active ? 'Deactivate' : 'Activate'}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => openDeleteModal(item)}
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
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Coupons</h1>
          <p className="text-xs text-muted-foreground mt-1">Create, edit and manage discount coupon lifecycle.</p>
        </div>
        <Button onClick={openAddModal} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm">
          <Plus size={16} /> Add Coupon
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 rounded-[14px] bg-white border-border shadow-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Total Coupons</div>
          <div className="text-xl font-bold text-foreground mt-1">{summary.total}</div>
        </Card>
        <Card className="p-4 rounded-[14px] bg-[#f4fbf4] border-[#d6efd6] shadow-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-[#2f7f2f]">Active</div>
          <div className="text-xl font-bold text-[#2f7f2f] mt-1">{summary.active}</div>
        </Card>
        <Card className="p-4 rounded-[14px] bg-[#fff6f3] border-[#ffd8cc] shadow-sm">
          <div className="text-xs font-bold uppercase tracking-wider text-[#bf5a2d]">Inactive</div>
          <div className="text-xl font-bold text-[#bf5a2d] mt-1">{summary.inactive}</div>
        </Card>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input
            placeholder="Search by code or type..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-10 shadow-none border-border/60 bg-muted/20"
          />
        </div>
        <select
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value as 'all' | 'active' | 'inactive')}
          className="h-10 min-w-[160px] rounded-xl border border-border/60 bg-background px-3 text-sm"
        >
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-10 text-muted-foreground text-xs uppercase tracking-widest animate-pulse">
          Loading coupons...
        </div>
      ) : (
        <DataTable data={filteredCoupons} columns={columns} actions={actions} onRowClick={openEditModal} />
      )}

      <Modal open={isModalOpen} onOpenChange={setIsModalOpen}>
        <ModalContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <ModalHeader>
            <ModalTitle>{editingCoupon ? 'Edit Coupon' : 'Add New Coupon'}</ModalTitle>
          </ModalHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4">
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Code</label>
              <Input
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                placeholder="WELCOME10"
                readOnly={!!editingCoupon}
                className={editingCoupon ? 'bg-muted/30 cursor-not-allowed' : ''}
              />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Type</label>
              <select
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value as CouponType })}
                className="flex h-11 w-full rounded-xl border border-border/60 bg-background px-3 py-2 text-sm"
              >
                <option value="percentage">Percentage</option>
                <option value="fixed">Fixed</option>
              </select>
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">
                Value {formData.type === 'percentage' ? '(%)' : '(₹)'}
              </label>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={formData.value}
                onChange={(e) => setFormData({ ...formData, value: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Max Discount (optional)</label>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={formData.max_discount}
                onChange={(e) => setFormData({ ...formData, max_discount: e.target.value })}
                placeholder="Only for percentage coupons"
              />
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Minimum Order Value</label>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={formData.min_order_value}
                onChange={(e) => setFormData({ ...formData, min_order_value: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Total Usage Limit (optional)</label>
              <Input
                type="number"
                min={1}
                value={formData.usage_limit}
                onChange={(e) => setFormData({ ...formData, usage_limit: e.target.value })}
              />
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Per User Limit (optional)</label>
              <Input
                type="number"
                min={1}
                value={formData.per_user_limit}
                onChange={(e) => setFormData({ ...formData, per_user_limit: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Active</label>
              <select
                value={formData.is_active ? 'yes' : 'no'}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.value === 'yes' })}
                className="flex h-11 w-full rounded-xl border border-border/60 bg-background px-3 py-2 text-sm"
              >
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Start Date</label>
              <Input
                type="datetime-local"
                value={formData.start_date}
                onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">End Date</label>
              <Input
                type="datetime-local"
                value={formData.end_date}
                onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
              />
            </div>
          </div>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => setIsModalOpen(false)}
              className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={handleSave}
              className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
            >
              {editingCoupon ? 'Update Coupon' : 'Create Coupon'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal open={isDeleteModalOpen} onOpenChange={setIsDeleteModalOpen}>
        <ModalContent className="max-w-md">
          <ModalHeader>
            <ModalTitle>Delete Coupon</ModalTitle>
          </ModalHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground">Are you sure you want to delete this coupon?</p>
            {couponToDelete ? (
              <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm">
                <div className="font-semibold text-foreground">{couponToDelete.code}</div>
                <div className="text-xs text-muted-foreground mt-1 uppercase">{couponToDelete.type}</div>
              </div>
            ) : null}
          </div>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => setIsDeleteModalOpen(false)}
              className="rounded-xl border-primary/40 bg-white text-primary hover:bg-primary hover:text-primary-foreground"
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={handleDelete}
              className="rounded-xl border-red-300 bg-white text-red-600 hover:bg-red-600 hover:text-white"
            >
              Confirm Delete
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
};
