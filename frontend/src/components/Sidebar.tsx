'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, FileText, Users, BarChart3, Settings, HelpCircle, LogOut } from 'lucide-react';
import { auth, patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { useLanguage } from '@/lib/i18n';

export function Sidebar() {
  const pathname = usePathname();
  const [patientList, setPatientList] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { setSelectedPatient, refreshTrigger } = useAppStore();
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
    patients.list().then((data) => {
      setPatientList(data.items || []);
      setError(null);
    }).catch(err => {
      setError('Cannot connect to backend.');
    });
  }, [refreshTrigger]);

  const handleLogout = async () => {
    await auth.logout();
    window.location.href = '/login';
  };

  return (
    <aside className="w-64 h-screen border-r border-white/5 bg-slate-950/40 backdrop-blur-3xl flex flex-col shrink-0 shadow-2xl shadow-cyan-900/10 sticky top-0">
      {/* Logo Area */}
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(34,211,238,0.4)]">
          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <h1 className="font-bold text-xl tracking-widest text-slate-100">AETHEL</h1>
      </div>

      {/* Main Navigation */}
      <nav className="px-3 py-4 space-y-2">
        {NAV_ITEMS.map((item) => {
          // Highlight if active
          const isActive = pathname.startsWith(item.href);
          
          return (
            <Link 
              key={item.href} 
              href={item.href}
              className={`flex items-center gap-4 px-4 py-3 rounded-r-xl transition-all duration-300 relative ${
                isActive 
                  ? 'bg-gradient-to-r from-cyan-900/40 to-transparent text-cyan-300' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              {isActive && (
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-cyan-400 rounded-r-full shadow-[0_0_10px_rgba(34,211,238,0.8)]" />
              )}
              <item.icon className={`w-5 h-5 ${isActive ? 'text-cyan-400 drop-shadow-[0_0_5px_rgba(34,211,238,0.5)]' : ''}`} />
              <span className="font-medium tracking-wide">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Recent Patients */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 border-t border-white/5">
        <div className="text-[10px] font-bold uppercase tracking-widest text-cyan-500/50 px-4 py-2 mt-2">
          {t('nav.recentPatients')}
        </div>
        {error && (
          <div className="px-4 py-2 m-2 bg-red-950/30 border border-red-900/50 rounded-md text-xs text-red-400">
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
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-all duration-300 ${
                isActive 
                  ? 'bg-slate-800/50 text-cyan-300 shadow-sm border border-cyan-800/30' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
              }`}
            >
              <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]' : 'bg-slate-600'}`} />
              <span className="truncate">{p.pseudonym}</span>
            </Link>
          );
        })}
      </div>

      {/* Bottom Area */}
      <div className="p-4 mt-auto border-t border-white/5">
        <button 
          onClick={handleLogout} 
          className="flex w-full items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-950/30 transition-all duration-300"
        >
          <LogOut className="w-5 h-5" />
          <span className="font-medium tracking-wide">{t('nav.logout')}</span>
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
