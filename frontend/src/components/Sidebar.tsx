'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, FileText, Users, BarChart3, Settings, HelpCircle, LogOut, Stethoscope } from 'lucide-react';
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
    }).catch(() => {
      setError('Cannot connect to backend.');
    });
  }, [refreshTrigger]);

  const handleLogout = async () => {
    await auth.logout();
    window.location.href = '/login';
  };

  return (
    <aside className="w-64 h-screen border-r border-white/10 bg-[#080d15]/85 backdrop-blur-2xl flex flex-col shrink-0 shadow-2xl z-40 sticky top-0">
      {/* Brand Header */}
      <div className="p-6 flex items-center gap-3.5 border-b border-white/5">
        <div className="w-10 h-10 rounded-2xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-300 shadow-[0_0_15px_rgba(20,184,166,0.25)]">
          <Stethoscope className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-bold text-base tracking-tight text-slate-100">Clinical Copilot</h1>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
            <span className="text-[10px] font-mono text-teal-300/90 font-medium">AI ASSISTANT</span>
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
              className={`flex items-center gap-3.5 px-4 py-2.5 rounded-xl text-xs font-medium tracking-wide transition-all duration-200 relative ${
                isActive 
                  ? 'bg-teal-500/15 text-teal-200 border border-teal-500/30 shadow-sm shadow-teal-950/30' 
                  : 'text-slate-400 hover:text-slate-100 hover:bg-white/5'
              }`}
            >
              <item.icon className={`w-4 h-4 ${isActive ? 'text-teal-300' : 'text-slate-400'}`} />
              <span className="font-medium">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Recent Patients */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 border-t border-white/5 chat-scrollbar">
        <div className="text-[10px] font-bold uppercase tracking-widest text-teal-400/70 px-3 py-2">
          {t('nav.recentPatients')}
        </div>
        {error && (
          <div className="px-3 py-2 m-2 bg-rose-950/30 border border-rose-900/50 rounded-lg text-xs text-rose-300">
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
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all duration-200 ${
                isActive 
                  ? 'bg-teal-500/15 text-teal-200 border border-teal-500/30 font-medium' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? 'bg-teal-400 shadow-[0_0_6px_rgba(20,184,166,0.8)]' : 'bg-slate-600'}`} />
              <span className="truncate">{p.pseudonym}</span>
            </Link>
          );
        })}
      </div>

      {/* Bottom Logout Area */}
      <div className="p-4 mt-auto border-t border-white/5">
        <button 
          onClick={handleLogout} 
          className="flex w-full items-center gap-3 px-4 py-2.5 rounded-xl text-xs text-slate-400 hover:text-rose-300 hover:bg-rose-950/20 transition-all duration-200"
        >
          <LogOut className="w-4 h-4" />
          <span className="font-medium">{t('nav.logout')}</span>
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
