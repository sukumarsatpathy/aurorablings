import React from 'react';
import { ShieldCheck, CreditCard, Mail, Truck, Palette, LockKeyhole, Tags, LineChart, Activity } from 'lucide-react';
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
  const trackingItems: Array<{ key: SettingsCategoryMenu; label: string; icon: React.ElementType }> = [
    { key: 'gtm_settings', label: 'GTM Settings', icon: Tags },
    { key: 'pixel_settings', label: 'Pixel Settings', icon: Activity },
    { key: 'analytics_settings', label: 'Analytics Settings', icon: LineChart },
    { key: 'clarity_settings', label: 'Clarity Settings', icon: Activity },
  ];

  return (
    <div className="space-y-3 rounded-2xl border border-border/70 bg-white p-2">
      <div className="space-y-1">
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

      <div className="border-t border-border/70 pt-2">
        <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Tracking</p>
        <div className="space-y-1">
          {trackingItems.map((item) => {
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
      </div>
    </div>
  );
};
