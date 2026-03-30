import React, { useEffect, useMemo, useState } from 'react';
import { DataTable } from '@/components/admin/AdminTable';
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
import catalogService, { type CatalogAdminAttribute } from '@/services/api/catalog';

interface AttributeFormState {
  name: string;
  options: string;
  is_active: boolean;
}

const DEFAULT_FORM: AttributeFormState = {
  name: '',
  options: '',
  is_active: true,
};

const extractRows = (payload: any): any[] => {
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.data?.results)) return payload.data.results;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload)) return payload;
  return [];
};

export const Attributes: React.FC = () => {
  const [attributes, setAttributes] = useState<CatalogAdminAttribute[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingAttr, setEditingAttr] = useState<CatalogAdminAttribute | null>(null);
  const [formData, setFormData] = useState<AttributeFormState>(DEFAULT_FORM);
  const [isSaving, setIsSaving] = useState(false);

  const [attributeToDelete, setAttributeToDelete] = useState<CatalogAdminAttribute | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const attrRes = await catalogService.listAttributes({ search: searchTerm.trim() || undefined });
      setAttributes(extractRows(attrRes) as CatalogAdminAttribute[]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const columns = [
    { header: 'ID', accessorKey: 'id', className: 'text-xs text-muted-foreground w-20' },
    {
      header: 'Attribute Name',
      accessorKey: 'name',
      cell: (item: CatalogAdminAttribute) => <div className="font-bold text-foreground">{item.name}</div>,
    },
    {
      header: 'Options',
      accessorKey: 'options',
      cell: (item: CatalogAdminAttribute) => (
        <div className="flex flex-wrap gap-1">
          {(item.options || []).map((opt: string, i: number) => (
            <Badge key={`${opt}-${i}`} variant="surface" className="text-[10px]">{opt}</Badge>
          ))}
        </div>
      ),
    },
    {
      header: 'Products Using',
      accessorKey: 'linked_products',
      align: 'right' as const,
      cell: (item: CatalogAdminAttribute) => (
        <Badge variant="outline" className="text-[10px]">{item.linked_products || 0}</Badge>
      ),
    },
    {
      header: 'Status',
      accessorKey: 'is_active',
      align: 'right' as const,
      cell: (item: CatalogAdminAttribute) => (
        <Badge variant={item.is_active ? 'surface' : 'outline'} className="text-[10px]">
          {item.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
  ];

  const openEdit = (item: CatalogAdminAttribute) => {
    setEditingAttr(item);
    setFormData({
      name: item.name,
      options: (item.options || []).join(', '),
      is_active: item.is_active,
    });
    setIsModalOpen(true);
  };

  const openAdd = () => {
    setEditingAttr(null);
    setFormData(DEFAULT_FORM);
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      alert('Attribute name is required.');
      return;
    }

    const parsedOptions = formData.options
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      setIsSaving(true);
      if (editingAttr) {
        await catalogService.updateAttribute(editingAttr.id, {
          name: formData.name.trim(),
          options: parsedOptions,
          is_active: formData.is_active,
        });
      } else {
        await catalogService.createAttribute({
          name: formData.name.trim(),
          options: parsedOptions,
          is_active: formData.is_active,
        });
      }
      setIsModalOpen(false);
      await loadData();
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to save attribute.';
      alert(message);
    } finally {
      setIsSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!attributeToDelete) return;
    try {
      await catalogService.deleteAttribute(attributeToDelete.id);
      setAttributeToDelete(null);
      await loadData();
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to delete attribute.';
      alert(message);
    }
  };

  const actions = (item: CatalogAdminAttribute) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[160px]">
        <DropdownMenuItem onClick={() => openEdit(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Edit size={14} /> Edit Attribute
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setAttributeToDelete(item)} className="flex items-center gap-2 cursor-pointer text-xs text-destructive focus:text-destructive">
          <Trash2 size={14} /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const filteredAttributes = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return attributes;
    return attributes.filter((a) => `${a.name} ${(a.options || []).join(' ')}`.toLowerCase().includes(q));
  }, [attributes, searchTerm]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Attributes</h1>
          <p className="text-xs text-muted-foreground mt-1">Manage global attributes and options reusable across products.</p>
        </div>
        <Button onClick={openAdd} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm">
          <Plus size={16} /> Add Attribute
        </Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input
            placeholder="Search by attribute or option..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-10 shadow-none border-border/60 bg-muted/20"
          />
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">
          Loading attributes...
        </div>
      ) : (
        <DataTable data={filteredAttributes} columns={columns} actions={actions} onRowClick={(item) => openEdit(item)} />
      )}

      <Modal open={isModalOpen} onOpenChange={setIsModalOpen}>
        <ModalContent>
          <ModalHeader>
            <ModalTitle>{editingAttr ? 'Edit Attribute' : 'Add New Attribute'}</ModalTitle>
          </ModalHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium">Attribute Name</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="e.g. Size"
              />
            </div>

            <div className="grid gap-2">
              <label className="text-sm font-medium">Options (Comma separated)</label>
              <Input
                value={formData.options}
                onChange={(e) => setFormData((prev) => ({ ...prev, options: e.target.value }))}
                placeholder="e.g. S, M, L, XL"
              />
            </div>

            <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData((prev) => ({ ...prev, is_active: e.target.checked }))}
              />
              Active
            </label>
          </div>

          <ModalFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)} disabled={isSaving}>Cancel</Button>
            <Button onClick={handleSave} disabled={isSaving}>{isSaving ? 'Saving...' : 'Save Changes'}</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <ConfirmDialog
        open={Boolean(attributeToDelete)}
        onOpenChange={(open) => {
          if (!open) setAttributeToDelete(null);
        }}
        title="Delete Attribute"
        description="This will delete this global attribute. Existing product mappings for this attribute will be removed."
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={confirmDelete}
      />
    </div>
  );
};
