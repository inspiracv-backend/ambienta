'use client';

import { useState, type ReactNode } from 'react';
import { AppHeader, AppSidebar } from '@/components/organisms';

/** Header + sidebar persistentes (H1); sidebar colapsa a drawer en mobile (RNF-15). Sin lógica de negocio ni fetching real — eso vive en app/(dashboard)/*. */
export function DashboardLayout({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader onOpenMobileNav={() => setMobileNavOpen(true)} />
      <div className="flex flex-1">
        <AppSidebar mobileOpen={mobileNavOpen} onMobileOpenChange={setMobileNavOpen} />
        <main className="min-w-0 flex-1 bg-slate-50 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
