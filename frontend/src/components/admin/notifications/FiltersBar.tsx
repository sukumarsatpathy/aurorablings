import React from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export interface NotificationLogFilters {
  search: string;
  status: string;
  channel: string;
  provider: string;
  notification_type: string;
  date_from: string;
  date_to: string;
}

interface Props {
  filters: NotificationLogFilters;
  onChange: (next: NotificationLogFilters) => void;
  onApply: () => void;
  loading?: boolean;
}

const STATUS_OPTIONS = ['', 'pending', 'sent', 'failed', 'retrying', 'cancelled'];
const CHANNEL_OPTIONS = ['', 'email', 'sms', 'whatsapp', 'push'];
const PROVIDER_OPTIONS = ['', 'smtp', 'brevo', 'twilio', 'internal', 'other'];

export const FiltersBar: React.FC<Props> = ({ filters, onChange, onApply, loading }) => {
  const patch = (key: keyof NotificationLogFilters, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="grid grid-cols-1 gap-3 rounded-2xl border border-border/70 bg-white p-4 lg:grid-cols-12">
      <div className="lg:col-span-3">
        <Input
          value={filters.search}
          onChange={(e) => patch('search', e.target.value)}
          placeholder="Search recipient, subject, error"
          className="h-10"
        />
      </div>
      <div className="lg:col-span-2">
        <select className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm" value={filters.status} onChange={(e) => patch('status', e.target.value)}>
          {STATUS_OPTIONS.map((value) => (
            <option key={value || 'all'} value={value}>{value ? value.toUpperCase() : 'All Status'}</option>
          ))}
        </select>
      </div>
      <div className="lg:col-span-2">
        <select className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm" value={filters.channel} onChange={(e) => patch('channel', e.target.value)}>
          {CHANNEL_OPTIONS.map((value) => (
            <option key={value || 'all'} value={value}>{value ? value.toUpperCase() : 'All Channels'}</option>
          ))}
        </select>
      </div>
      <div className="lg:col-span-2">
        <select className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm" value={filters.provider} onChange={(e) => patch('provider', e.target.value)}>
          {PROVIDER_OPTIONS.map((value) => (
            <option key={value || 'all'} value={value}>{value ? value.toUpperCase() : 'All Providers'}</option>
          ))}
        </select>
      </div>
      <div className="lg:col-span-1">
        <Input type="date" value={filters.date_from} onChange={(e) => patch('date_from', e.target.value)} className="h-10" />
      </div>
      <div className="lg:col-span-1">
        <Input type="date" value={filters.date_to} onChange={(e) => patch('date_to', e.target.value)} className="h-10" />
      </div>
      <div className="lg:col-span-1">
        <Button className="h-10 w-full" onClick={onApply} disabled={loading}>{loading ? '...' : 'Apply'}</Button>
      </div>
    </div>
  );
};
