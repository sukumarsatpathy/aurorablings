import React, { useEffect, useMemo, useState } from 'react';
import { DataTable } from '@/components/admin/AdminTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Plus, Search, MoreHorizontal, Edit, Trash2, X, ArrowUp, ArrowDown } from 'lucide-react';
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
import { isColourName, swatchColour, swatchFor } from '@/lib/variantOptions';

interface OptionRow {
  /** Local row id for React keys. */
  rowId: string;
  value: string;
  /** "#RRGGBB" or "" (none set). */
  hex: string;
}

interface AttributeFormState {
  name: string;
  rows: OptionRow[];
  is_active: boolean;
  show_swatches: boolean;
  /** The swatch switch was touched by hand (stop following the name). */
  swatchesTouched: boolean;
}

const DEFAULT_FORM: AttributeFormState = {
  name: '',
  rows: [],
  is_active: true,
  show_swatches: false,
  swatchesTouched: false,
};

let rowCounter = 0;
const newRow = (value: string, hex = ''): OptionRow => ({ rowId: `opt-${(rowCounter += 1)}`, value, hex });

/** '#b7410e' / 'B7410E' → '#B7410E'; '' → ''; anything else → null (invalid). */
const normaliseHex = (raw: string): string | null => {
  const value = raw.trim();
  if (!value) return '';
  const withHash = value.startsWith('#') ? value : `#${value}`;
  return /^#[0-9a-f]{6}$/i.test(withHash) ? withHash.toUpperCase() : null;
};

const hexByOption = (item: CatalogAdminAttribute): Record<string, string> =>
  Object.fromEntries((item.option_details || []).map((d) => [d.value.toLowerCase(), d.hex_code || '']));

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
  const [newOptions, setNewOptions] = useState('');

  /** "Rust, Wine" → rows, skipping ones already in the list. */
  const parseNewOptions = (text: string, existing: OptionRow[]): OptionRow[] => {
    const seen = new Set(existing.map((r) => r.value.trim().toLowerCase()));
    const rows: OptionRow[] = [];
    for (const part of text.split(',')) {
      const value = part.trim();
      if (!value || seen.has(value.toLowerCase())) continue;
      seen.add(value.toLowerCase());
      rows.push(newRow(value));
    }
    return rows;
  };

  const addNewOptions = () => {
    setFormData((prev) => ({ ...prev, rows: [...prev.rows, ...parseNewOptions(newOptions, prev.rows)] }));
    setNewOptions('');
  };

  const updateRow = (rowId: string, patch: Partial<OptionRow>) => {
    setFormData((prev) => ({ ...prev, rows: prev.rows.map((r) => (r.rowId === rowId ? { ...r, ...patch } : r)) }));
  };

  const removeRow = (rowId: string) => {
    setFormData((prev) => ({ ...prev, rows: prev.rows.filter((r) => r.rowId !== rowId) }));
  };

  const moveRow = (index: number, delta: number) => {
    setFormData((prev) => {
      const rows = [...prev.rows];
      const target = index + delta;
      if (target < 0 || target >= rows.length) return prev;
      [rows[index], rows[target]] = [rows[target], rows[index]];
      return { ...prev, rows };
    });
  };

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
      cell: (item: CatalogAdminAttribute) => {
        const hexes = hexByOption(item);
        return (
          <div className="flex flex-wrap gap-1">
            {(item.options || []).map((opt: string, i: number) => {
              const dot = item.show_swatches ? swatchColour(opt, hexes[opt.toLowerCase()]) : null;
              return (
                <Badge key={`${opt}-${i}`} variant="surface" className="inline-flex items-center gap-1 text-[10px]">
                  {dot ? <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full border border-black/15" style={{ background: dot }} /> : null}
                  {opt}
                </Badge>
              );
            })}
          </div>
        );
      },
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
    const hexes = hexByOption(item);
    setFormData({
      name: item.name,
      rows: (item.options || []).map((opt) => newRow(opt, hexes[opt.toLowerCase()] || '')),
      is_active: item.is_active,
      show_swatches: item.show_swatches ?? isColourName(item.name),
      swatchesTouched: true,
    });
    setNewOptions('');
    setIsModalOpen(true);
  };

  const openAdd = () => {
    setEditingAttr(null);
    setFormData(DEFAULT_FORM);
    setNewOptions('');
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      alert('Attribute name is required.');
      return;
    }

    // Fold in anything still typed in the "add options" box.
    const rows = [...formData.rows, ...parseNewOptions(newOptions, formData.rows)];
    const parsedOptions = rows.map((r) => r.value.trim()).filter(Boolean);
    const optionColors: Record<string, string> = {};
    for (const row of rows) {
      const value = row.value.trim();
      if (!value) continue;
      const hex = normaliseHex(row.hex);
      if (hex === null) {
        alert(`"${row.hex}" for ${value} isn't a colour code. Use 6 hex digits, e.g. #B7410E.`);
        return;
      }
      optionColors[value] = hex;
    }

    const payload = {
      name: formData.name.trim(),
      options: parsedOptions,
      is_active: formData.is_active,
      show_swatches: formData.show_swatches,
      option_colors: optionColors,
    };

    try {
      setIsSaving(true);
      if (editingAttr) {
        await catalogService.updateAttribute(editingAttr.id, payload);
      } else {
        await catalogService.createAttribute(payload);
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
                onChange={(e) => {
                  const name = e.target.value;
                  setFormData((prev) => ({
                    ...prev,
                    name,
                    show_swatches: prev.swatchesTouched ? prev.show_swatches : isColourName(name),
                  }));
                }}
                placeholder="e.g. Size"
              />
            </div>

            <label className="flex items-start gap-2 rounded-lg border border-border/70 bg-muted/20 p-3 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={formData.show_swatches}
                onChange={(e) => setFormData((prev) => ({ ...prev, show_swatches: e.target.checked, swatchesTouched: true }))}
              />
              <span>
                <span className="font-medium">Show as colour swatches</span>
                <span className="block text-xs text-muted-foreground">
                  Options appear as colour dots on the product page. Turn on for Color, off for things like Size.
                </span>
              </span>
            </label>

            <div className="grid gap-2">
              <label className="text-sm font-medium">Options</label>
              {formData.rows.length === 0 ? (
                <p className="text-xs text-muted-foreground">No options yet. Add some below.</p>
              ) : (
                <div className="max-h-[320px] space-y-1.5 overflow-y-auto pr-1">
                  {formData.rows.map((row, index) => {
                    const valid = normaliseHex(row.hex);
                    const guess = swatchFor(row.value);
                    const pickerValue = (valid || guess || '#CCCCCC').toString();
                    return (
                      <div key={row.rowId} className="flex items-center gap-2 rounded-lg border border-border/60 bg-white px-2 py-1.5">
                        <div className="flex flex-col">
                          <button type="button" aria-label={`Move ${row.value} up`} disabled={index === 0} onClick={() => moveRow(index, -1)} className="text-muted-foreground disabled:opacity-30 hover:text-foreground"><ArrowUp size={12} /></button>
                          <button type="button" aria-label={`Move ${row.value} down`} disabled={index === formData.rows.length - 1} onClick={() => moveRow(index, 1)} className="text-muted-foreground disabled:opacity-30 hover:text-foreground"><ArrowDown size={12} /></button>
                        </div>
                        {formData.show_swatches ? (
                          <>
                            <label
                              className={`relative h-8 w-8 shrink-0 cursor-pointer overflow-hidden rounded-full border ${valid ? 'border-black/20' : 'border-dashed border-black/30'}`}
                              title={valid ? `Pick a colour for ${row.value}` : `No colour set — showing a guess from the name. Click to pick one.`}
                              style={{ background: valid || guess || 'transparent', opacity: valid ? 1 : 0.55 }}
                            >
                              <input
                                type="color"
                                aria-label={`Colour for ${row.value}`}
                                value={/^#[0-9a-f]{6}$/i.test(pickerValue) ? pickerValue : '#CCCCCC'}
                                onChange={(e) => updateRow(row.rowId, { hex: e.target.value.toUpperCase() })}
                                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                              />
                            </label>
                            <Input
                              value={row.hex}
                              onChange={(e) => updateRow(row.rowId, { hex: e.target.value })}
                              onBlur={() => {
                                const hex = normaliseHex(row.hex);
                                if (hex !== null) updateRow(row.rowId, { hex });
                              }}
                              placeholder="#RRGGBB"
                              aria-label={`Hex code for ${row.value}`}
                              aria-invalid={valid === null}
                              className={`h-8 w-24 shrink-0 font-mono text-xs uppercase ${valid === null ? 'border-red-400 focus-visible:ring-red-300' : ''}`}
                              maxLength={7}
                            />
                          </>
                        ) : null}
                        <Input
                          value={row.value}
                          onChange={(e) => updateRow(row.rowId, { value: e.target.value })}
                          aria-label="Option name"
                          className="h-8 flex-1 text-sm"
                        />
                        <button type="button" onClick={() => removeRow(row.rowId)} aria-label={`Remove ${row.value}`} className="shrink-0 rounded p-1 text-muted-foreground hover:bg-red-50 hover:text-red-600">
                          <X size={14} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="flex gap-2">
                <Input
                  value={newOptions}
                  onChange={(e) => setNewOptions(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addNewOptions();
                    }
                  }}
                  placeholder="Add options, e.g. Rust, Wine, Peacock Blue"
                  className="h-9 text-sm"
                />
                <Button type="button" variant="outline" className="h-9" onClick={addNewOptions}>Add</Button>
              </div>
              {formData.show_swatches ? (
                <p className="text-[11px] text-muted-foreground">
                  Click a dot to pick a colour, or paste a hex code. Faded dots have no colour set yet and show a guess from the name.
                </p>
              ) : null}
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
