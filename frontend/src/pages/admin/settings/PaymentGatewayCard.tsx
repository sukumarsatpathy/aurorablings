import React, { useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DynamicFormRenderer } from './DynamicFormRenderer';
import type { PluginSettingBundle } from './types';

interface Props {
  bundle: PluginSettingBundle;
  value: Record<string, unknown>;
  saving?: boolean;
  canEdit: boolean;
  onChange: (next: Record<string, unknown>) => void;
  onSave: () => void;
}

export const PaymentGatewayCard: React.FC<Props> = ({
  bundle,
  value,
  saving = false,
  canEdit,
  onChange,
  onSave,
}) => {
  const rawOriginal = bundle.configSetting?.typed_value;
  const original = (rawOriginal && typeof rawOriginal === 'object') ? rawOriginal as Record<string, unknown> : {};
  const dirty = useMemo(() => JSON.stringify(original) !== JSON.stringify(value), [original, value]);
  const editingAllowed = canEdit && (bundle.configSetting?.is_editable ?? true);

  return (
    <Card className="rounded-2xl border border-border/70 bg-white p-4 shadow-sm">
      <details open className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-foreground">{bundle.title}</h3>
            <p className="text-xs text-muted-foreground">{bundle.schema.description || `${bundle.title} gateway configuration`}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={dirty ? 'default' : 'outline'} className="text-[10px] uppercase">
              {dirty ? 'Unsaved' : 'Saved'}
            </Badge>
          </div>
        </summary>

        <div className="mt-4 space-y-4">
          <DynamicFormRenderer
            schema={bundle.schema}
            value={value}
            disabled={!editingAllowed || saving}
            onChange={onChange}
          />

          <div className="rounded-xl border border-border/60 bg-muted/10 p-3 text-xs text-muted-foreground">
            <p><span className="font-semibold text-foreground">Config Key:</span> {bundle.configKey}</p>
            <p><span className="font-semibold text-foreground">Last Updated:</span> {bundle.configSetting?.updated_at ? new Date(bundle.configSetting.updated_at).toLocaleString() : 'Not created yet'}</p>
            <p><span className="font-semibold text-foreground">Editable:</span> {(bundle.configSetting?.is_editable ?? true) ? 'Yes' : 'No'}</p>
            <p><span className="font-semibold text-foreground">Public:</span> {(bundle.configSetting?.is_public ?? false) ? 'Yes' : 'No'}</p>
          </div>

          <div className="flex justify-end">
            <Button onClick={onSave} disabled={!editingAllowed || !dirty || saving}>
              {saving ? 'Saving...' : 'Save Gateway'}
            </Button>
          </div>
        </div>
      </details>
    </Card>
  );
};

