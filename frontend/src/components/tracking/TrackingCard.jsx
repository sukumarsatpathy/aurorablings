import { Loader2, Save, FlaskConical } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import ToggleSwitch from '@/components/tracking/ToggleSwitch';
import InputField from '@/components/tracking/InputField';

const TrackingCard = ({
  title,
  description,
  providerKey,
  enabled,
  idValue,
  placeholder,
  fieldName,
  error,
  loading = false,
  saving = false,
  onToggle,
  onIdChange,
  onSave,
  onTest,
}) => {
  const isBusy = loading || saving;

  return (
    <Card className="h-full border-border/60 bg-card/95 shadow-sm hover:translate-y-0 hover:shadow-md">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="text-base font-semibold text-foreground">{title}</CardTitle>
          <Badge variant={enabled ? 'default' : 'outline'} className={enabled ? 'bg-emerald-600 text-white' : ''}>
            {enabled ? 'Active' : 'Inactive'}
          </Badge>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="flex items-center justify-between rounded-xl border border-border/60 bg-background/60 px-3 py-2">
          <div>
            <p className="text-sm font-medium text-foreground">Enable Tracking</p>
            <p className="text-xs text-muted-foreground">Inject script dynamically on valid config.</p>
          </div>
          <ToggleSwitch
            id={`toggle-${providerKey}`}
            checked={enabled}
            disabled={isBusy}
            onChange={onToggle}
            ariaLabel={`Toggle ${title} tracking`}
          />
        </div>

        <InputField
          id={`tracking-id-${providerKey}`}
          label="Tracking ID"
          value={idValue}
          placeholder={placeholder}
          disabled={isBusy}
          error={error}
          onChange={(value) => onIdChange(fieldName, value)}
        />

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={isBusy}
            onClick={onTest}
            className="w-full rounded-xl"
          >
            <FlaskConical className="mr-2 h-4 w-4" />
            Test
          </Button>

          <Button
            type="button"
            size="sm"
            disabled={isBusy}
            onClick={onSave}
            className="w-full rounded-xl"
          >
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default TrackingCard;
