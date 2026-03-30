import { useMemo, useState } from 'react';
import { Copy, FileJson, Info } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/Drawer';
import { Tooltip } from '@/components/ui/Tooltip';
import { StatusBadge } from '@/components/admin/health/StatusBadge';
import type { HealthDetailCardData } from '@/types/health';

interface HealthCardProps {
  item: HealthDetailCardData;
  onCopyMessage: (text: string) => void;
  tooltipText?: string;
}

export function HealthCard({ item, onCopyMessage, tooltipText }: HealthCardProps) {
  const [isMetadataOpen, setIsMetadataOpen] = useState(false);

  const metadataText = useMemo(() => JSON.stringify(item.metadata ?? {}, null, 2), [item.metadata]);
  const showCopyButton = item.status === 'warning' || item.status === 'degraded' || item.status === 'down';

  return (
    <>
      <Card className="border-border/50 bg-card/95">
        <CardContent className="space-y-4 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <p className="text-sm font-semibold text-foreground">{item.name}</p>
                {tooltipText ? (
                  <Tooltip content={tooltipText}>
                    <button
                      type="button"
                      aria-label={`${item.name} explanation`}
                      className="rounded-md p-0.5 text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <Info className="h-3.5 w-3.5" />
                    </button>
                  </Tooltip>
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground">{item.metricLabel}</p>
            </div>
            <StatusBadge status={item.status} />
          </div>

          <div className="flex items-center justify-between gap-4">
            <p className="text-xl font-bold tracking-tight text-foreground">{item.metricValue}</p>
            {item.statusCode ? (
              <p className="rounded-full bg-muted/70 px-2.5 py-1 text-xs font-medium text-muted-foreground">
                HTTP {item.statusCode}
              </p>
            ) : null}
          </div>

          <p className="text-xs text-muted-foreground">{item.message}</p>

          <div className="flex items-center justify-between gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 rounded-lg px-2.5 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setIsMetadataOpen(true)}
            >
              <FileJson className="mr-1.5 h-3.5 w-3.5" />
              Metadata
            </Button>

            {showCopyButton ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-8 rounded-lg px-2.5 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => onCopyMessage(item.message)}
              >
                <Copy className="mr-1.5 h-3.5 w-3.5" />
                Copy error
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Drawer open={isMetadataOpen} onOpenChange={setIsMetadataOpen}>
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>{item.name} metadata</DrawerTitle>
            <DrawerDescription>Full raw payload from the monitoring backend.</DrawerDescription>
          </DrawerHeader>
          <pre className="h-[65vh] overflow-auto rounded-xl border border-border/60 bg-muted/30 p-4 text-xs leading-5 text-foreground md:h-[82vh]">
            {metadataText}
          </pre>
        </DrawerContent>
      </Drawer>
    </>
  );
}
