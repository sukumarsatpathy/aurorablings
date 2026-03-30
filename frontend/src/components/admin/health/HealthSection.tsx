import type { ReactNode } from 'react';

interface HealthSectionProps {
  title: string;
  description: string;
  children: ReactNode;
}

export function HealthSection({ title, description, children }: HealthSectionProps) {
  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {children}
    </section>
  );
}
