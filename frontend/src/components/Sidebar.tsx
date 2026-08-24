'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { LayoutDashboard, FileText, Users, BarChart3, Settings, HelpCircle, LogOut, Stethoscope, Sun, Moon } from 'lucide-react';
import { auth, patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { useLanguage } from '@/lib/i18n';

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [patientList, setPatientList] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { setSelectedPatient, refreshTrigger, darkMode, setDarkMode } = useAppStore();
  const { t } = useLanguage();

  const NAV_ITEMS = [
    { name: t('nav.dashboard'), href: '/dashboard', icon: LayoutDashboard },
    { name: t('nav.caseFiles'), href: '/case-files', icon: FileText },
    { name: t('nav.patients'), href: '/patients', icon: Users },
    { name: t('nav.analytics'), href: '/analytics', icon: BarChart3 },
    { name: t('nav.settings'), href: '/settings', icon: Settings },
    { name: t('nav.help'), href: '/help', icon: HelpCircle },
  ];

  useEffect(() => {
    patients.list({ page_size: 50 }).then((data) => {
      setPatientList(data.items || []);
      setError(null);
    }).catch(() => {
      setError('Cannot connect to backend.');
    });
  }, [refreshTrigger]);

  const handleLogout = async () => {
    await auth.logout();
    router.replace('/login');
  };

  return (
    <aside className="w-64 h-screen border-r border-slate-200/80 dark:border-white/10 bg-white dark:bg-[#080d15]/85 backdrop-blur-2xl flex flex-col shrink-0 shadow-sm dark:shadow-2xl z-40 sticky top-0 transition-colors">
      {/* Brand Header */}
      <div className="p-5 sm:p-6 flex items-center gap-3.5 border-b border-slate-100 dark:border-white/5">
        <div className="w-10 h-10 rounded-2xl bg-teal-500/10 dark:bg-teal-500/15 border border-teal-500/30 flex items-center justify-center text-teal-600 dark:text-teal-300 shadow-sm">
          <Stethoscope className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-extrabold text-base tracking-tight text-slate-900 dark:text-slate-100">Clinical Copilot</h1>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="w-1.5 h-1.5 rounded-full bg-teal-500 dark:bg-teal-400 animate-pulse" />
            <span className="text-[10px] font-mono text-teal-700 dark:text-teal-300/90 font-bold uppercase tracking-wider">AI ASSISTANT</span>
          </div>
        </div>
      </div>

      {/* Main Navigation */}
      <nav className="px-3 py-4 space-y-1.5">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3.5 px-4 py-2.5 rounded-xl text-xs tracking-wide transition-all duration-200 relative ${isActive
                  ? 'bg-teal-600 text-white font-bold shadow-sm shadow-teal-600/30 dark:bg-teal-500/15 dark:text-teal-200 dark:border dark:border-teal-500/30'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 font-medium dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-white/5'
                }`}
            >
              <item.icon className={`w-4 h-4 ${isActive ? 'text-white dark:text-teal-300' : 'text-slate-400 dark:text-slate-400'}`} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Recent Patients */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 border-t border-slate-100 dark:border-white/5 chat-scrollbar">
        <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-teal-400/70 px-3 py-2">
          {t('nav.recentPatients')}
        </div>
        {error && (
          <div className="px-3 py-2 m-2 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/50 rounded-lg text-xs text-rose-600 dark:text-rose-300">
            {error}
          </div>
        )}
        {patientList.map((p) => {
          const isActive = pathname.includes(`/patients/${p.patient_id}`);
          return (
            <Link
              key={p.patient_id}
              href={`/patients/${p.patient_id}`}
              onClick={() => setSelectedPatient(p)}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all duration-200 ${isActive
                  ? 'bg-teal-50 text-teal-800 font-bold border border-teal-200 dark:bg-teal-500/15 dark:text-teal-200 dark:border-teal-500/30'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70 font-medium dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-white/5'
                }`}
            >
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? 'bg-teal-500 dark:bg-teal-400 shadow-[0_0_6px_rgba(20,184,166,0.8)]' : 'bg-slate-400 dark:bg-slate-600'}`} />
              <span className="truncate">{p.pseudonym}</span>
            </Link>
          );
        })}
      </div>

      {/* Bottom Actions: Theme Toggle & Logout */}
      <div className="p-3.5 mt-auto border-t border-slate-200/80 dark:border-white/5 space-y-1">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="flex w-full items-center justify-between px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-white/5 transition-all duration-200 cursor-pointer"
        >
          <div className="flex items-center gap-3">
            {darkMode ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-600" />}
            <span>{darkMode ? 'Giao diện Sáng' : 'Giao diện Tối'}</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-white/10 text-slate-500 dark:text-slate-400">
            {darkMode ? 'DARK' : 'LIGHT'}
          </span>
        </button>

        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-rose-600 hover:bg-rose-50 dark:text-slate-400 dark:hover:text-rose-300 dark:hover:bg-rose-950/20 transition-all duration-200 cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
          <span>{t('nav.logout')}</span>
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
