import React from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { NotificationProviderStatus } from '@/services/api/adminNotifications';

interface Props {
  providers: NotificationProviderStatus[];
  testingId: number | null;
  onTest: (providerId: number) => void;
}

export const ProviderStatusCards: React.FC<Props> = ({ providers, testingId, onTest }) => {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {providers.map((provider) => (
        <Card key={provider.id} className="rounded-2xl border border-border/70 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold uppercase">{provider.provider_type}</h3>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${provider.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-muted text-muted-foreground'}`}>
              {provider.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Last Test: {provider.last_tested_at ? new Date(provider.last_tested_at).toLocaleString() : 'Never'}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Result: {provider.last_test_status || 'N/A'}
          </p>
          <p className="mt-1 min-h-10 text-xs text-muted-foreground">{provider.last_test_message || 'No diagnostics yet.'}</p>

          <div className="mt-3">
            <Button className="h-9" onClick={() => onTest(provider.id)} disabled={testingId === provider.id}>
              {testingId === provider.id ? 'Testing...' : 'Test Provider'}
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
};
