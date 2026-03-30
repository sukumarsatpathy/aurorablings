import React from 'react';
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from '@/components/ui/Drawer';
import type { NotificationLogDetail } from '@/services/api/adminNotifications';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  data: NotificationLogDetail | null;
}

const pretty = (value: unknown) => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? '');
  }
};

export const NotificationDetailDrawer: React.FC<Props> = ({ open, onOpenChange, data }) => {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>Notification Detail</DrawerTitle>
          <DrawerDescription>Inspect payload, rendered content, provider response, and errors.</DrawerDescription>
        </DrawerHeader>

        {!data ? (
          <div className="text-sm text-muted-foreground">No log selected.</div>
        ) : (
          <div className="space-y-4 overflow-y-auto pr-1 max-h-[calc(100vh-140px)]">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><strong>Recipient:</strong> {data.recipient || '—'}</div>
              <div><strong>Status:</strong> {data.status}</div>
              <div><strong>Provider:</strong> {data.provider}</div>
              <div><strong>Template:</strong> {data.template_name || '—'}</div>
              <div><strong>Attempts:</strong> {data.attempts_count}</div>
              <div><strong>Created:</strong> {new Date(data.created_at).toLocaleString()}</div>
            </div>

            <section>
              <h4 className="text-sm font-semibold">Error</h4>
              <div className="mt-1 rounded-lg border border-border bg-muted/20 p-3 text-xs whitespace-pre-wrap">
                {data.error_message || 'No error'}
              </div>
            </section>

            <section>
              <h4 className="text-sm font-semibold">Context JSON</h4>
              <pre className="mt-1 overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-xs">{pretty(data.rendered_context_json)}</pre>
            </section>

            <section>
              <h4 className="text-sm font-semibold">HTML Snapshot</h4>
              <pre className="mt-1 overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-xs">{data.rendered_html_snapshot || ''}</pre>
            </section>

            <section>
              <h4 className="text-sm font-semibold">Plain Text Snapshot</h4>
              <pre className="mt-1 overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-xs">{data.plain_text_snapshot || ''}</pre>
            </section>

            <section>
              <h4 className="text-sm font-semibold">Provider Response</h4>
              <pre className="mt-1 overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-xs">{pretty(data.raw_response)}</pre>
            </section>
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
};
