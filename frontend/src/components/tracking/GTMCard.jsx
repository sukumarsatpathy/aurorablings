import { Loader2, Save, FlaskConical } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import ToggleSwitch from '@/components/tracking/ToggleSwitch';

const badgeVariantByStatus = {
  Active: 'bg-emerald-600 text-white',
  Disabled: '',
  Invalid: 'bg-destructive text-destructive-foreground',
  'Not Configured': '',
};

export default function GTMCard({
  enabled,
  gtmId,
  validationMessage,
  status,
  loading,
  saving,
  canSave,
  onToggle,
  onIdChange,
  onSave,
  onTest,
}) {
  const busy = loading || saving;
  const badgeClassName = badgeVariantByStatus[status] || '';

  return (
    <Card className="border-border/60 bg-card shadow-sm">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base font-semibold text-foreground">GTM Configuration</CardTitle>
          <Badge variant={status === 'Active' || status === 'Invalid' ? 'default' : 'outline'} className={badgeClassName}>
            {status}
          </Badge>
        </div>
        <CardDescription>Enable GTM and configure your container ID for storefront tracking.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center justify-between rounded-xl border border-border/70 bg-background/60 px-3 py-2">
          <div>
            <p className="text-sm font-medium text-foreground">Enable GTM</p>
            <p className="text-xs text-muted-foreground">Scripts are injected dynamically at runtime.</p>
          </div>
          <ToggleSwitch
            id="gtm-enable"
            checked={enabled}
            disabled={busy}
            onChange={onToggle}
            ariaLabel="Enable Google Tag Manager"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="gtm-container-id" className="text-sm font-medium text-foreground/90">
            GTM Container ID
          </label>
          <Input
            id="gtm-container-id"
            value={gtmId}
            onChange={(event) => onIdChange(event.target.value)}
            placeholder="GTM-XXXX"
            autoComplete="off"
            spellCheck={false}
            disabled={busy}
            className={validationMessage ? 'border-destructive/70 focus-visible:border-destructive' : ''}
          />
          {validationMessage ? <p className="text-xs text-destructive">{validationMessage}</p> : null}
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Button type="button" variant="outline" size="sm" disabled={busy} onClick={onTest} className="rounded-xl">
            <FlaskConical className="mr-2 h-4 w-4" />
            Test
          </Button>
          <Button type="button" size="sm" disabled={!canSave || busy} onClick={onSave} className="rounded-xl">
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
