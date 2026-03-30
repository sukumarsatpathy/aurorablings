import React, { useMemo, useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import type { DynamicFormSchema } from './types';

interface Props {
  schema: DynamicFormSchema;
  value: Record<string, unknown>;
  disabled?: boolean;
  onChange: (next: Record<string, unknown>) => void;
}

export const DynamicFormRenderer: React.FC<Props> = ({ schema, value, disabled = false, onChange }) => {
  const [visibleSecrets, setVisibleSecrets] = useState<Record<string, boolean>>({});

  const entries = useMemo(() => Object.entries(schema.fields), [schema.fields]);
  const asBool = (raw: unknown): boolean => {
    if (typeof raw === 'boolean') return raw;
    if (typeof raw === 'string') {
      const v = raw.trim().toLowerCase();
      if (['true', '1', 'yes', 'on'].includes(v)) return true;
      if (['false', '0', 'no', 'off', ''].includes(v)) return false;
    }
    if (typeof raw === 'number') return raw !== 0;
    return Boolean(raw);
  };

  return (
    <div className="space-y-4">
      {entries.map(([fieldKey, field]) => {
        const currentValue = value[fieldKey];
        const commonLabel = (
          <div className="flex items-center gap-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{field.label}</span>
            {field.required ? <span className="text-destructive">*</span> : null}
          </div>
        );

        if (field.type === 'toggle') {
          const checked = asBool(currentValue);
          return (
            <div key={fieldKey} className="rounded-xl border border-border/70 bg-muted/10 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  {commonLabel}
                  {field.description ? <p className="text-xs text-muted-foreground mt-1">{field.description}</p> : null}
                </div>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onChange({ ...value, [fieldKey]: !checked })}
                  className={`relative h-6 w-10 overflow-hidden rounded-full transition-colors ${checked ? 'bg-primary' : 'bg-border'} ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
                  aria-label={field.label}
                >
                  <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${checked ? 'translate-x-4' : 'translate-x-0'}`} />
                </button>
              </div>
            </div>
          );
        }

        if (field.type === 'select') {
          return (
            <div key={fieldKey} className="grid gap-2">
              {commonLabel}
              <select
                disabled={disabled}
                className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={String(currentValue ?? '')}
                onChange={(e) => onChange({ ...value, [fieldKey]: e.target.value })}
              >
                {(field.options || []).map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {field.description ? <p className="text-xs text-muted-foreground">{field.description}</p> : null}
            </div>
          );
        }

        if (field.type === 'password') {
          const show = Boolean(visibleSecrets[fieldKey]);
          return (
            <div key={fieldKey} className="grid gap-2">
              {commonLabel}
              <div className="flex gap-2">
                <Input
                  type={show ? 'text' : 'password'}
                  value={String(currentValue ?? '')}
                  placeholder={field.placeholder}
                  disabled={disabled}
                  onChange={(e) => onChange({ ...value, [fieldKey]: e.target.value })}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="shrink-0"
                  onClick={() => setVisibleSecrets((prev) => ({ ...prev, [fieldKey]: !show }))}
                >
                  {show ? 'Hide' : 'Show'}
                </Button>
              </div>
              {field.description ? <p className="text-xs text-muted-foreground">{field.description}</p> : null}
            </div>
          );
        }

        return (
          <div key={fieldKey} className="grid gap-2">
            {commonLabel}
            <Input
              type="text"
              value={String(currentValue ?? '')}
              placeholder={field.placeholder}
              disabled={disabled}
              onChange={(e) => onChange({ ...value, [fieldKey]: e.target.value })}
            />
            {field.description ? <p className="text-xs text-muted-foreground">{field.description}</p> : null}
          </div>
        );
      })}
    </div>
  );
};
