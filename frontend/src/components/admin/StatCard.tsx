import React from 'react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/Card';

interface StatCardProps {
  label: string;
  value: string | number;
  trend?: {
    value: number;
    label: string;
    isPositive: boolean;
  };
  variant?: 'default' | 'primary' | 'cyan' | 'purple';
  className?: string;
  children?: React.ReactNode;
}

export const StatCard: React.FC<StatCardProps> = ({ 
  label, 
  value, 
  trend, 
  variant = 'default',
  className,
  children
}) => {
  const isDefault = variant === 'default';
  
  return (
    <Card 
      className={cn(
        "p-5 rounded-[14px] border border-border shadow-sm flex flex-col justify-between overflow-hidden relative",
        {
          "bg-white text-foreground": variant === 'default',
          "bg-primary text-white border-primary": variant === 'primary',
          "bg-[#5bc4c0] text-white border-[#5bc4c0]": variant === 'cyan',
          "bg-[#7c6fd4] text-white border-[#7c6fd4]": variant === 'purple',
        },
        className
      )}
    >
      <div>
        <div className={cn("text-[11px] font-medium opacity-80 mb-1", !isDefault && "text-white/80")}>
          {label}
        </div>
        
        <div className="flex items-center justify-between mt-1">
           <div className="text-[28px] font-bold leading-none tracking-tight">
             {value}
           </div>
           
           {/* Optional chart/graphic slot on the right */}
           {children && <div className="ml-4">{children}</div>}
        </div>
      </div>

      {trend && (
        <div className="flex items-center gap-1 mt-4 text-xs font-medium">
          <span 
            className={cn(
               "px-1.5 py-0.5 rounded flex items-center gap-0.5",
               trend.isPositive 
                 ? (isDefault ? "text-[#517b4b] bg-[#517b4b]/10" : "text-white bg-white/20")
                 : (isDefault ? "text-destructive bg-destructive/10" : "text-white bg-white/20")
            )}
          >
            {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
          </span>
          <span className={cn("opacity-70", !isDefault && "text-white/70")}>{trend.label}</span>
        </div>
      )}
    </Card>
  );
};
