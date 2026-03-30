import React from 'react';
import { Sidebar, Topbar } from '@/components/admin/LayoutComponents';
import { useBranding } from '@/hooks/useBranding';

interface LayoutProps {
  children: React.ReactNode;
}

export const DashboardLayout: React.FC<LayoutProps> = ({ children }) => {
  const currentYear = new Date().getFullYear();
  const branding = useBranding();
  const footerText = branding.footerText || `© ${currentYear} ${branding.brandName}. All Rights are reserved.`;

  return (
    <div className="flex h-screen overflow-hidden bg-background font-sans selection:bg-primary/20 selection:text-primary">
      {/* Sidebar Rail */}
      <Sidebar />

      {/* Main Content Area */}
      <div
        className="flex flex-1 flex-col overflow-y-auto px-6 py-4 md:px-8 md:py-6 transition-all duration-300"
        data-lenis-prevent
      >
        <Topbar />
        <main className="flex-1 pb-8">
          {children}
        </main>
        <footer className="border-t border-border/60 py-4 text-center text-xs text-muted-foreground">
          {footerText}
        </footer>
      </div>
    </div>
  );
};
