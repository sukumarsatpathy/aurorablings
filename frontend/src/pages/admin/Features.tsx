import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { DataTable, StatusBadge } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Plus, Search, MoreHorizontal, Edit, Trash2, Power, SlidersHorizontal, X } from 'lucide-react';
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
import featureService from '@/services/api/features';
import type { Feature, FeatureCategory, FeatureTier, FeatureWriteData } from '@/types/feature';

type FeatureFormState = {
  code: string;
  name: string;
  description: string;
  category: FeatureCategory;
  tier: FeatureTier;
  requires_config: boolean;
  config_schema_text: string;
  is_available: boolean;
  is_enabled: boolean;
  rollout_percentage: number;
};

type LiveFilter = 'all' | 'enabled' | 'disabled';
type ToastVariant = 'success' | 'error' | 'info';
type ToastMessage = { id: string; variant: ToastVariant; message: string };

const DEFAULT_FORM: FeatureFormState = {
  code: '',
  name: '',
  description: '',
  category: 'general',
  tier: 'free',
  requires_config: false,
  config_schema_text: '{}',
  is_available: true,
  is_enabled: false,
  rollout_percentage: 100,
};

const CATEGORIES: FeatureCategory[] = [
  'general',
  'payment',
  'notification',
  'shipping',
  'catalog',
  'order',
  'analytics',
  'marketing',
  'security',
];

const TIERS: FeatureTier[] = ['free', 'basic', 'premium', 'enterprise'];

export const Features: React.FC = () => {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<'all' | FeatureCategory>('all');
  const [liveFilter, setLiveFilter] = useState<LiveFilter>('all');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingFeature, setEditingFeature] = useState<Feature | null>(null);
  const [featureToDelete, setFeatureToDelete] = useState<Feature | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [formData, setFormData] = useState<FeatureFormState>(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const pushToast = useCallback((variant: ToastVariant, message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { id, variant, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 2800);
  }, []);

  const fetchFeatures = async () => {
    try {
      setLoading(true);
      const response = await featureService.getAll();
      setFeatures(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to fetch features:', error);
      pushToast('error', 'Failed to load features.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeatures();
  }, [pushToast]);

  const filteredFeatures = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return features.filter((f) => {
      const matchesSearch = !q || `${f.code} ${f.name} ${f.category} ${f.tier}`.toLowerCase().includes(q);
      const matchesCategory = categoryFilter === 'all' || f.category === categoryFilter;
      const isEnabled = !!f.flag?.is_enabled;
      const matchesLive = liveFilter === 'all' || (liveFilter === 'enabled' ? isEnabled : !isEnabled);
      return matchesSearch && matchesCategory && matchesLive;
    });
  }, [features, searchTerm, categoryFilter, liveFilter]);

  const totals = useMemo(() => {
    const total = features.length;
    const live = features.filter((f) => f.flag?.is_enabled).length;
    const requiresConfig = features.filter((f) => f.requires_config).length;
    return { total, live, requiresConfig };
  }, [features]);

  const openAddModal = () => {
    setEditingFeature(null);
    setFormData(DEFAULT_FORM);
    setFormError('');
    setIsModalOpen(true);
  };

  const openEditModal = (feature: Feature) => {
    setEditingFeature(feature);
    setFormData({
      code: feature.code,
      name: feature.name,
      description: feature.description || '',
      category: feature.category,
      tier: feature.tier,
      requires_config: feature.requires_config,
      config_schema_text: JSON.stringify(feature.config_schema || {}, null, 2),
      is_available: feature.is_available,
      is_enabled: !!feature.flag?.is_enabled,
      rollout_percentage: feature.flag?.rollout_percentage ?? 100,
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const openDeleteModal = (feature: Feature) => {
    setFeatureToDelete(feature);
    setIsDeleteModalOpen(true);
  };

  const handleDelete = async () => {
    if (!featureToDelete) return;
    try {
      await featureService.delete(featureToDelete.code);
      setIsDeleteModalOpen(false);
      setFeatureToDelete(null);
      pushToast('success', 'Feature deleted successfully.');
      fetchFeatures();
    } catch {
      pushToast('error', 'Failed to delete feature.');
    }
  };

  const handleQuickToggle = async (feature: Feature) => {
    try {
      if (feature.flag?.is_enabled) {
        await featureService.disable(feature.code, 'Disabled from Features menu');
      } else {
        await featureService.enable(feature.code, 'Enabled from Features menu');
      }
      pushToast('success', `Feature ${feature.flag?.is_enabled ? 'disabled' : 'enabled'}.`);
      fetchFeatures();
    } catch {
      pushToast('error', 'Failed to update feature status.');
    }
  };

  const handleSave = async () => {
    setFormError('');
    let parsedSchema: Record<string, unknown> = {};
    try {
      parsedSchema = formData.config_schema_text.trim()
        ? JSON.parse(formData.config_schema_text)
        : {};
    } catch {
      setFormError('Config schema must be valid JSON.');
      return;
    }

    const payload: FeatureWriteData = {
      code: formData.code.trim(),
      name: formData.name.trim(),
      description: formData.description.trim(),
      category: formData.category,
      tier: formData.tier,
      requires_config: formData.requires_config,
      config_schema: parsedSchema,
      is_available: formData.is_available,
    };

    if (!payload.code || !payload.name) {
      setFormError('Code and name are required.');
      return;
    }

    try {
      setSaving(true);
      const targetCode = editingFeature?.code || payload.code;

      if (editingFeature) {
        await featureService.update(targetCode, payload);
      } else {
        await featureService.create(payload);
      }

      if (formData.is_enabled) {
        await featureService.enable(targetCode, 'Updated from Features modal');
      } else {
        await featureService.disable(targetCode, 'Updated from Features modal');
      }

      await featureService.setRollout(targetCode, formData.rollout_percentage);

      setIsModalOpen(false);
      pushToast('success', editingFeature ? 'Feature updated successfully.' : 'Feature created successfully.');
      fetchFeatures();
    } catch (error) {
      console.error(error);
      setFormError('Failed to save feature. Please verify inputs and try again.');
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    { header: 'Code', accessorKey: 'code', className: 'text-xs text-muted-foreground' },
    {
      header: 'Name',
      accessorKey: 'name',
      cell: (item: Feature) => <div className="font-bold text-foreground">{item.name}</div>,
    },
    {
      header: 'Category',
      accessorKey: 'category',
      cell: (item: Feature) => <Badge variant="surface" className="text-[10px] uppercase">{item.category}</Badge>,
    },
    {
      header: 'Tier',
      accessorKey: 'tier',
      cell: (item: Feature) => <Badge variant="outline" className="text-[10px] uppercase">{item.tier}</Badge>,
    },
    {
      header: 'Requires Config',
      accessorKey: 'requires_config',
      cell: (item: Feature) => <StatusBadge status={item.requires_config ? 'Enabled' : 'Disabled'} />,
    },
    {
      header: 'Live',
      accessorKey: 'is_enabled',
      cell: (item: Feature) => <StatusBadge status={item.flag?.is_enabled ? 'Active' : 'Inactive'} />,
      align: 'center' as const,
    },
    {
      header: 'Rollout',
      accessorKey: 'rollout_percentage',
      cell: (item: Feature) => (
        <span className="text-xs font-semibold">{item.flag?.rollout_percentage ?? 100}%</span>
      ),
      align: 'right' as const,
    },
  ];

  const actions = (item: Feature) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[190px]">
        <DropdownMenuItem onClick={() => openEditModal(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Edit size={14} /> Edit Feature
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleQuickToggle(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Power size={14} /> {item.flag?.is_enabled ? 'Disable' : 'Enable'}
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
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Features</h1>
          <p className="text-xs text-muted-foreground mt-1">Manage feature catalogue and runtime rollout controls.</p>
        </div>
        <Button onClick={openAddModal} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm">
          <Plus size={16} /> Add Feature
        </Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input
            placeholder="Search features by code, name, category, or tier..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-10 shadow-none border-border/60 bg-muted/20"
          />
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as 'all' | FeatureCategory)}
          className="h-10 rounded-xl border border-border/60 bg-background px-3 text-sm min-w-[160px]"
        >
          <option value="all">All categories</option>
          {CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
        <select
          value={liveFilter}
          onChange={(e) => setLiveFilter(e.target.value as LiveFilter)}
          className="h-10 rounded-xl border border-border/60 bg-background px-3 text-sm min-w-[140px]"
        >
          <option value="all">All status</option>
          <option value="enabled">Enabled</option>
          <option value="disabled">Disabled</option>
        </select>
        <Button
          variant="outline"
          onClick={() => {
            setSearchTerm('');
            setCategoryFilter('all');
            setLiveFilter('all');
          }}
          className="h-10 rounded-xl border-primary/30 bg-white text-primary"
        >
          <X size={14} className="mr-1" /> Clear
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-border/70 bg-white p-4">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Total Features</p>
          <p className="mt-1 text-2xl font-bold text-foreground">{totals.total}</p>
        </div>
        <div className="rounded-2xl border border-border/70 bg-white p-4">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Live Features</p>
          <p className="mt-1 text-2xl font-bold text-primary">{totals.live}</p>
        </div>
        <div className="rounded-2xl border border-border/70 bg-white p-4">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Needs Config</p>
          <p className="mt-1 text-2xl font-bold text-foreground">{totals.requiresConfig}</p>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-10 text-muted-foreground text-xs uppercase tracking-widest animate-pulse">
          Loading features...
        </div>
      ) : (
        <DataTable
          data={filteredFeatures}
          columns={columns}
          actions={actions}
          onRowClick={openEditModal}
        />
      )}

      <Modal open={isModalOpen} onOpenChange={setIsModalOpen}>
        <ModalContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <ModalHeader>
            <ModalTitle>{editingFeature ? 'Edit Feature' : 'Add New Feature'}</ModalTitle>
          </ModalHeader>
          {formError ? (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {formError}
            </div>
          ) : null}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-4">
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Code *</label>
              <Input
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                placeholder="payment_stripe"
                readOnly={!!editingFeature}
                className={[
                  editingFeature ? 'bg-muted/30 cursor-not-allowed' : '',
                  !formData.code.trim() ? 'border-destructive/40' : '',
                ].join(' ')}
              />
            </div>
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Name *</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Stripe Payments"
                className={!formData.name.trim() ? 'border-destructive/40' : ''}
              />
            </div>

            <div className="grid gap-2 md:col-span-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="w-full rounded-xl border border-border/60 bg-background px-4 py-2 text-sm"
                placeholder="Feature purpose and usage notes"
              />
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Category</label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value as FeatureCategory })}
                className="flex h-11 w-full rounded-xl border border-border/60 bg-background px-3 py-2 text-sm"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Tier</label>
              <select
                value={formData.tier}
                onChange={(e) => setFormData({ ...formData, tier: e.target.value as FeatureTier })}
                className="flex h-11 w-full rounded-xl border border-border/60 bg-background px-3 py-2 text-sm"
              >
                {TIERS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            <div className="grid gap-2 md:col-span-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Config Schema (JSON)</label>
              <textarea
                value={formData.config_schema_text}
                onChange={(e) => setFormData({ ...formData, config_schema_text: e.target.value })}
                rows={8}
                className="w-full rounded-xl border border-border/60 bg-background px-4 py-2 text-sm font-mono"
                placeholder='{"API_KEY": {"type": "string", "required": true}}'
              />
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Rollout %</label>
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={14} className="text-muted-foreground" />
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={formData.rollout_percentage}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      rollout_percentage: Math.max(0, Math.min(100, Number(e.target.value || 0))),
                    })
                  }
                />
              </div>
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Flags</label>
              <div className="rounded-xl border border-border/60 bg-muted/20 p-3 space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.requires_config}
                    onChange={(e) => setFormData({ ...formData, requires_config: e.target.checked })}
                  />
                  Requires provider config
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.is_available}
                    onChange={(e) => setFormData({ ...formData, is_available: e.target.checked })}
                  />
                  Globally available
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.is_enabled}
                    onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                  />
                  Enabled now
                </label>
              </div>
            </div>
          </div>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => setIsModalOpen(false)}
              className="rounded-xl border-primary/40 bg-white text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm"
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={handleSave}
              disabled={saving}
              className="rounded-xl border-primary/40 bg-white px-6 font-bold text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground hover:shadow-sm disabled:opacity-60"
            >
              {saving ? 'Saving...' : editingFeature ? 'Update Feature' : 'Create Feature'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <Modal open={isDeleteModalOpen} onOpenChange={setIsDeleteModalOpen}>
        <ModalContent className="max-w-md">
          <ModalHeader>
            <ModalTitle>Delete Feature</ModalTitle>
          </ModalHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground">Are you sure you want to delete this feature?</p>
            {featureToDelete && (
              <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm">
                <div className="font-semibold text-foreground">{featureToDelete.name}</div>
                <div className="text-xs text-muted-foreground mt-1">{featureToDelete.code}</div>
              </div>
            )}
          </div>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => setIsDeleteModalOpen(false)}
              className="rounded-xl border-primary/40 bg-white text-primary transition-all duration-300 hover:-translate-y-0.5 hover:border-primary hover:bg-primary hover:text-primary-foreground"
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={handleDelete}
              className="rounded-xl border-red-300 bg-white text-red-600 transition-all duration-300 hover:-translate-y-0.5 hover:border-red-600 hover:bg-red-600 hover:text-white"
            >
              Confirm Delete
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <div className="pointer-events-none fixed right-5 top-5 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={[
              'rounded-xl border bg-white px-4 py-3 text-sm shadow-lg',
              toast.variant === 'success' ? 'border-emerald-300 text-emerald-700' : '',
              toast.variant === 'error' ? 'border-destructive/40 text-destructive' : '',
              toast.variant === 'info' ? 'border-blue-300 text-blue-700' : '',
            ].join(' ')}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
};
