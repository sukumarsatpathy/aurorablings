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
  if (s === 'cancelled' || s === 'refunded' || s === 'out of stock') return <Badge variant="destructive" className="text-[10px]">{status}</Badge>;
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
}

export function DataTable<T>({ data, columns, onRowClick, actions }: DataTableProps<T>) {
  return (
    <div className="bg-white rounded-[14px] border border-border shadow-sm overflow-hidden">
      <Table>
        <TableHeader className="bg-muted/10">
          <TableRow className="hover:bg-transparent">
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
              <TableCell colSpan={columns.length + (actions ? 1 : 0)} className="h-24 text-center text-muted-foreground">
                No results found.
              </TableCell>
            </TableRow>
          ) : (
            data.map((item, rowIndex) => (
              <TableRow 
                key={rowIndex} 
                onClick={() => onRowClick && onRowClick(item)}
                className={cn("hover:bg-muted/30 transition-colors", onRowClick && "cursor-pointer")}
              >
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
