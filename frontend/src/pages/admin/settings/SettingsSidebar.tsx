import React from 'react';
import { ShieldCheck, CreditCard, Mail, Truck, Palette, LockKeyhole } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SettingsCategoryMenu } from './types';

const items: Array<{ key: SettingsCategoryMenu; label: string; icon: React.ElementType }> = [
  { key: 'general', label: 'General', icon: ShieldCheck },
  { key: 'branding', label: 'Branding', icon: Palette },
  { key: 'payment', label: 'Payment', icon: CreditCard },
  { key: 'notification', label: 'Notification', icon: Mail },
  { key: 'shipping', label: 'Shipping', icon: Truck },
  { key: 'advanced', label: 'Security', icon: LockKeyhole },
];

interface Props {
  active: SettingsCategoryMenu;
  onChange: (next: SettingsCategoryMenu) => void;
}

export const SettingsSidebar: React.FC<Props> = ({ active, onChange }) => {
  return (
    <div className="space-y-1 rounded-2xl border border-border/70 bg-white p-2">
      {items.map((item) => {
        const Icon = item.icon;
        const isActive = active === item.key;
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => onChange(item.key)}
            className={cn(
              'flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
            )}
          >
            <Icon size={16} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
};
