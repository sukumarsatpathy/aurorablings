import React, { useEffect, useMemo, useState } from 'react';
import { DataTable } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Plus, Search, MoreHorizontal, Edit, Trash2, FolderTree } from 'lucide-react';
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
import UploadOverlay from '@/components/ui/UploadOverlay';
import catalogService from '@/services/api/catalog';
import { LabelPaperPicture } from '@/components/admin/LabelPaperPicture';
import { DEFAULT_LABEL_PAPER, LABEL_PAPERS, labelPaper, type LabelPaperKey } from '@/lib/labelPapers';

interface Category {
  id: string;
  name: string;
  slug: string;
  parent: string | null;
  parent_name: string | null;
  description: string;
  is_active: boolean;
  sort_order: number;
  /** Which barcode label roll this category's products print on. */
  label_paper?: LabelPaperKey;
  product_count: number;
  image?: string;
}

interface CategoryFormState {
  name: string;
  parent: string | null;
  description: string;
  is_active: boolean;
  sort_order: number;
  label_paper: LabelPaperKey;
  image: File | null;
}

const DEFAULT_FORM: CategoryFormState = {
  name: '',
  parent: null,
  description: '',
  is_active: true,
  sort_order: 0,
  label_paper: DEFAULT_LABEL_PAPER,
  image: null,
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

export const CategoryManagement: React.FC = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [formData, setFormData] = useState<CategoryFormState>(DEFAULT_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);

  const [categoryToDelete, setCategoryToDelete] = useState<Category | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await catalogService.listCategories();
      setCategories(extractRows(res) as Category[]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const columns = [
    { header: 'ID', accessorKey: 'id', className: 'text-xs text-muted-foreground w-20' },
    {
      header: 'Category Name',
      accessorKey: 'name',
      cell: (item: Category) => (
        <div className="flex flex-col">
          <div className="font-bold text-foreground">{item.name}</div>
          <div className="text-[10px] text-muted-foreground">{item.slug}</div>
        </div>
      ),
    },
    {
      header: 'Parent',
      accessorKey: 'parent_name',
      cell: (item: Category) => (
        item.parent_name ? (
          <Badge variant="surface" className="text-[10px] border-primary/20 bg-primary/5 text-primary">
            {item.parent_name}
          </Badge>
        ) : (
          <span className="text-[10px] text-muted-foreground">—</span>
        )
      ),
    },
    {
      header: 'Products',
      accessorKey: 'product_count',
      align: 'center' as const,
      cell: (item: Category) => (
        <Badge variant={item.product_count > 0 ? "surface" : "outline"} className="text-[10px]">
          {item.product_count || 0}
        </Badge>
      ),
    },
    {
      header: 'Label paper',
      accessorKey: 'label_paper',
      cell: (item: Category) => {
        const paper = labelPaper(item.label_paper);
        return (
          <div className="flex flex-col">
            <span className="text-xs font-medium">{paper.name}</span>
            <span className="text-[10px] text-muted-foreground">{paper.size}</span>
          </div>
        );
      },
    },
    {
      header: 'Order',
      accessorKey: 'sort_order',
      align: 'center' as const,
      cell: (item: Category) => <span className="text-xs font-medium">{item.sort_order}</span>,
    },
    {
      header: 'Status',
      accessorKey: 'is_active',
      align: 'right' as const,
      cell: (item: Category) => (
        <Badge variant={item.is_active ? 'surface' : 'outline'} className={item.is_active ? "text-[10px] bg-emerald-50 text-emerald-700 border-emerald-100" : "text-[10px]"}>
          {item.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
  ];

  const openEdit = (item: Category) => {
    setEditingCategory(item);
    setFormData({
      name: item.name,
      parent: item.parent,
      description: item.description || '',
      is_active: item.is_active,
      sort_order: item.sort_order || 0,
      label_paper: labelPaper(item.label_paper).key,
      image: null,
    });
    setIsModalOpen(true);
  };

  const openAdd = () => {
    setEditingCategory(null);
    setFormData(DEFAULT_FORM);
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      alert('Category name is required.');
      return;
    }

    const data = new FormData();
    data.append('name', formData.name.trim());
    if (formData.parent) data.append('parent', formData.parent);
    data.append('description', formData.description.trim());
    data.append('is_active', String(formData.is_active));
    data.append('sort_order', String(formData.sort_order));
    data.append('label_paper', formData.label_paper);
    if (formData.image) data.append('image', formData.image);

    try {
      setIsSaving(true);
      const onProgress = formData.image ? (percent: number) => setUploadPercent(percent) : undefined;
      if (formData.image) setUploadPercent(0);
      if (editingCategory) {
        await catalogService.updateCategory(editingCategory.id, data, onProgress);
      } else {
        await catalogService.createCategory(data, onProgress);
      }
      setIsModalOpen(false);
      await loadData();
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to save category.';
      alert(message);
    } finally {
      setIsSaving(false);
      setUploadPercent(null);
    }
  };

  const confirmDelete = async () => {
    if (!categoryToDelete) return;
    try {
      await catalogService.deleteCategory(categoryToDelete.id);
      setCategoryToDelete(null);
      await loadData();
    } catch (error: any) {
      const message = error?.response?.data?.message || 'Failed to delete category.';
      alert(message);
    }
  };

  const actions = (item: Category) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[160px]">
        <DropdownMenuItem onClick={() => openEdit(item)} className="flex items-center gap-2 cursor-pointer text-xs">
          <Edit size={14} /> Edit Category
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setCategoryToDelete(item)} className="flex items-center gap-2 cursor-pointer text-xs text-destructive focus:text-destructive">
          <Trash2 size={14} /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const filteredCategories = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter((c) =>
      c.name.toLowerCase().includes(q) ||
      (c.parent_name && c.parent_name.toLowerCase().includes(q))
    );
  }, [categories, searchTerm]);

  // Options for parent category dropdown
  const parentOptions = useMemo(() => {
    return categories
      .filter(c => !editingCategory || c.id !== editingCategory.id) // Cannot be own parent
      .map(c => ({ id: c.id, name: c.name }));
  }, [categories, editingCategory]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <FolderTree className="text-primary" size={24} />
            Categories
          </h1>
          <p className="text-xs text-muted-foreground mt-1">Manage product categories and hierarchy.</p>
        </div>
        <Button onClick={openAdd} className="shrink-0 h-10 gap-2 font-bold px-4 rounded-xl shadow-sm">
          <Plus size={16} /> Add Category
        </Button>
      </div>

      <div className="bg-white p-4 rounded-[14px] border border-border shadow-sm flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
          <Input
            placeholder="Search categories..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-10 shadow-none border-border/60 bg-muted/20"
          />
        </div>
      </div>

      {loading ? (
        <div className="rounded-[14px] border border-border bg-white p-8 text-center text-sm text-muted-foreground">
          Loading categories...
        </div>
      ) : (
        <DataTable data={filteredCategories} columns={columns} actions={actions} onRowClick={(item) => openEdit(item)} />
      )}

      <Modal open={isModalOpen} onOpenChange={setIsModalOpen}>
        <ModalContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <ModalHeader>
            <ModalTitle>{editingCategory ? 'Edit Category' : 'Add New Category'}</ModalTitle>
          </ModalHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Category Name</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="e.g. Rings"
              />
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Parent Category</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={formData.parent || ''}
                onChange={(e) => setFormData((prev) => ({ ...prev, parent: e.target.value || null }))}
              >
                <option value="">None (Root Category)</option>
                {parentOptions.map(opt => (
                  <option key={opt.id} value={opt.id}>{opt.name}</option>
                ))}
              </select>
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Description</label>
              <textarea
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={formData.description}
                onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="Brief description of the category..."
              />
            </div>

            <div className="grid gap-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Category Icon / Image</label>
              <div className="flex items-center gap-4">
                {editingCategory?.image && !formData.image && (
                  <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center overflow-hidden border border-border">
                    <img src={editingCategory.image} alt="Current" className="w-full h-full object-cover" />
                  </div>
                )}
                <Input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    if (!file) {
                      setFormData((prev) => ({ ...prev, image: null }));
                      return;
                    }
                    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
                      alert('Only JPG, PNG, and WEBP images are allowed.');
                      e.target.value = '';
                      return;
                    }
                    if (file.size > MAX_IMAGE_SIZE_BYTES) {
                      alert('Image must be 5 MB or smaller.');
                      e.target.value = '';
                      return;
                    }
                    setFormData((prev) => ({ ...prev, image: file }));
                  }}
                  className="flex-1"
                />
              </div>
              <p className="text-[10px] text-muted-foreground italic">Recommended: Square JPG, PNG, or WEBP up to 5 MB.</p>
            </div>

            {/*
              Which roll this category's barcode labels print on. Both papers
              carry the same data; the picture shows where it sits on each, so
              the label printer app's template can be set up to match.
            */}
            <fieldset className="grid gap-2">
              <legend className="mb-2 text-xs font-bold uppercase text-muted-foreground">Barcode Label Paper</legend>
              {LABEL_PAPERS.map((paper) => {
                const selected = formData.label_paper === paper.key;
                return (
                  <label
                    key={paper.key}
                    className={`flex cursor-pointer flex-col gap-2 rounded-xl border p-3 transition-colors ${
                      selected ? 'border-primary bg-primary/5 ring-1 ring-inset ring-primary' : 'border-border hover:border-primary/40'
                    }`}
                  >
                    <span className="flex items-start gap-2">
                      <input
                        type="radio"
                        name="label_paper"
                        value={paper.key}
                        checked={selected}
                        onChange={() => setFormData((prev) => ({ ...prev, label_paper: paper.key }))}
                        className="mt-0.5 h-4 w-4 accent-primary"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-baseline gap-x-2">
                          <span className="text-sm font-semibold text-foreground">{paper.name}</span>
                          <span className="text-xs font-medium text-primary">{paper.size}</span>
                        </span>
                        <span className="block text-[11px] text-muted-foreground">{paper.material}</span>
                        <span className="block text-[11px] text-muted-foreground">{paper.use}</span>
                      </span>
                    </span>
                    <LabelPaperPicture paper={paper.key} className="h-auto w-full max-h-28" />
                  </label>
                );
              })}
            </fieldset>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Sort Order</label>
                <Input
                  type="number"
                  value={formData.sort_order}
                  onChange={(e) => setFormData((prev) => ({ ...prev, sort_order: parseInt(e.target.value) || 0 }))}
                />
              </div>
              <div className="flex items-center gap-2 pt-6">
                <input
                  type="checkbox"
                  id="category-active"
                  className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                  checked={formData.is_active}
                  onChange={(e) => setFormData((prev) => ({ ...prev, is_active: e.target.checked }))}
                />
                <label htmlFor="category-active" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                  Active
                </label>
              </div>
            </div>
          </div>

          <ModalFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)} disabled={isSaving}>Cancel</Button>
            <Button onClick={handleSave} disabled={isSaving}>{isSaving ? 'Saving...' : 'Save Category'}</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      <UploadOverlay
        visible={isSaving}
        message={
          uploadPercent !== null
            ? (uploadPercent >= 100 ? 'Compressing image...' : 'Uploading category image...')
            : 'Saving category...'
        }
        percent={uploadPercent}
      />

      <ConfirmDialog
        open={Boolean(categoryToDelete)}
        onOpenChange={(open) => {
          if (!open) setCategoryToDelete(null);
        }}
        title="Delete Category"
        description={`Are you sure you want to delete the category "${categoryToDelete?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={confirmDelete}
      />
    </div>
  );
};
