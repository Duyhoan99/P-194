'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { useAppStore } from '@/lib/store';

export function RootLayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthPage = pathname === '/login';
  const isLandingPage = pathname === '/';
  const { darkMode, compactView } = useAppStore();

  useEffect(() => {
    // Apply dark mode class to html (this typically interacts with a real theme system)
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  useEffect(() => {
    // Apply compact view class to html or body
    if (compactView) {
      document.documentElement.classList.add('compact-mode');
    } else {
      document.documentElement.classList.remove('compact-mode');
    }
  }, [compactView]);

  if (isAuthPage || isLandingPage) {
    return <>{children}</>;
  }

  return (
    <div className="app-layout bg-transparent text-slate-100 min-h-screen flex">
      <Sidebar />
      <main className="main-content flex flex-col overflow-hidden relative bg-transparent w-full">
        {children}
      </main>
    </div>
  );
}
