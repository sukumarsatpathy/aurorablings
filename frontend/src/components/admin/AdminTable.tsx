import React from 'react';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';

// Utility for specific admin badges based on the design system
export const StatusBadge: React.FC<{ status: string; type?: 'order' | 'inventory' | 'generic' }> = ({ status }) => {
  const s = status.toLowerCase();
  
  // Mapping logic for standard ecommerce statuses to our UI variants
  if (s === 'processing' || s === 'pending') return <Badge variant="surface" className="text-[10px]">{status}</Badge>;
  if (s === 'shipped' || s === 'delivered' || s === 'in stock') return <Badge variant="default" className="text-[10px] bg-[#517b4b]">{status}</Badge>;
  if (s === 'cancelled' || s === 'refunded' || s === 'out of stock' || s === 'deleted') return <Badge variant="destructive" className="text-[10px]">{status}</Badge>;
  if (s === 'low stock') return <Badge variant="outline" className="text-[10px] border-[#c8a97e] text-[#c8a97e]">{status}</Badge>;
  
  return <Badge variant="outline" className="text-[10px]">{status}</Badge>;
}

interface Column<T> {
  header: string;
  accessorKey: keyof T | string;
  cell?: (item: T) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  onRowClick?: (item: T) => void;
  actions?: (item: T) => React.ReactNode;
  /**
   * Row selection. Opt-in: pass `getRowId` and the selection state and a
   * checkbox column appears. Tables that don't pass it are untouched.
   */
  getRowId?: (item: T) => string;
  selectedIds?: string[];
  onToggleRow?: (id: string) => void;
  onToggleAll?: (checked: boolean) => void;
}

export function DataTable<T>({
  data,
  columns,
  onRowClick,
  actions,
  getRowId,
  selectedIds,
  onToggleRow,
  onToggleAll,
}: DataTableProps<T>) {
  const selectable = Boolean(getRowId && selectedIds && onToggleRow);
  const selected = new Set(selectedIds || []);
  const pageIds = selectable ? data.map((item) => getRowId!(item)) : [];
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const someOnPageSelected = pageIds.some((id) => selected.has(id));
  return (
    <div className="bg-white rounded-[14px] border border-border shadow-sm overflow-hidden">
      <Table>
        <TableHeader className="bg-muted/10">
          <TableRow className="hover:bg-transparent">
            {selectable && (
              <TableHead className="w-[44px]">
                <input
                  type="checkbox"
                  aria-label="Select all rows on this page"
                  className="h-4 w-4 cursor-pointer rounded border-border align-middle"
                  checked={allOnPageSelected}
                  ref={(node) => {
                    if (node) node.indeterminate = !allOnPageSelected && someOnPageSelected;
                  }}
                  onChange={(event) => onToggleAll?.(event.target.checked)}
                />
              </TableHead>
            )}
            {columns.map((col, idx) => (
              <TableHead 
                key={idx} 
                className={cn(
                  "text-[11px] font-bold uppercase tracking-wider text-muted-foreground h-10",
                  col.align === 'right' && "text-right",
                  col.align === 'center' && "text-center",
                  col.className
                )}
              >
                {col.header}
              </TableHead>
            ))}
            {actions && <TableHead className="w-[80px]"></TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={columns.length + (actions ? 1 : 0) + (selectable ? 1 : 0)}
                className="h-24 text-center text-muted-foreground"
              >
                No results found.
              </TableCell>
            </TableRow>
          ) : (
            data.map((item, rowIndex) => (
              <TableRow 
                key={rowIndex} 
                onClick={() => onRowClick && onRowClick(item)}
                className={cn(
                  "hover:bg-muted/30 transition-colors",
                  onRowClick && "cursor-pointer",
                  selectable && selected.has(getRowId!(item)) && "bg-primary/5"
                )}
              >
                {selectable && (
                  <TableCell className="py-3" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label="Select row"
                      className="h-4 w-4 cursor-pointer rounded border-border align-middle"
                      checked={selected.has(getRowId!(item))}
                      onChange={() => onToggleRow!(getRowId!(item))}
                    />
                  </TableCell>
                )}
                {columns.map((col, colIndex) => (
                  <TableCell 
                    key={colIndex} 
                    className={cn(
                      "py-3 text-sm font-medium",
                      col.align === 'right' && "text-right",
                      col.align === 'center' && "text-center",
                      col.className
                    )}
                  >
                    {col.cell ? col.cell(item) : (item as any)[col.accessorKey]}
                  </TableCell>
                ))}
                {actions && (
                  <TableCell className="text-right py-2" onClick={(e) => e.stopPropagation()}>
                    {actions(item)}
                  </TableCell>
                )}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
