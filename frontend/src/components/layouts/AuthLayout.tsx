import React from 'react';
import { useBranding } from '@/hooks/useBranding';

interface LayoutProps {
  children: React.ReactNode;
}

export const AuthLayout: React.FC<LayoutProps> = ({ children }) => {
  const branding = useBranding();

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-start justify-center bg-transparent px-4 pt-6 pb-12 sm:pt-8">
      <div className="w-full max-w-md space-y-6 p-8 bg-white/95 rounded-2xl shadow-premium border border-border/50">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-primary">{branding.brandName}</h1>
          <p className="text-muted-foreground mt-2 text-sm">Welcome back</p>
        </div>
        {children}
      </div>
    </div>
  );
};
