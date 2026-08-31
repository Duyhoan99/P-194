'use client';
import { useEffect, useState } from 'react';
import { patients, ingestions } from '@/lib/api';
import { BarChart3, TrendingUp, Users, FileText, Activity, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';

export default function AnalyticsPage() {
  const [stats, setStats] = useState({
    totalPatients: 0,
    documentsProcessed: 0,
    accuracy: '0%',
    avgTime: '0s',
    loading: true
  });
  const { t } = useLanguage();

  useEffect(() => {
    const loadData = async () => {
      try {
        const [patientsRes, uploadsRes] = await Promise.allSettled([
          patients.list({ page: 1, page_size: 1 }),
          ingestions.list(100)
        ]);

        const ptData = patientsRes.status === 'fulfilled' ? patientsRes.value : null;
        const uploadsData = uploadsRes.status === 'fulfilled' ? uploadsRes.value : [];

        let totalDocs = 0;
        let successfulDocs = 0;
        let totalTimeMs = 0;
        let timedDocs = 0;

        if (Array.isArray(uploadsData)) {
          totalDocs = uploadsData.length;
          uploadsData.forEach((u: any) => {
            if (u.status === 'completed' || u.status === 'completed_with_warnings') {
              successfulDocs++;
            }
            if (u.received_at && u.completed_at) {
              const start = new Date(u.received_at).getTime();
              const end = new Date(u.completed_at).getTime();
              if (end > start) {
                totalTimeMs += (end - start);
                timedDocs++;
              }
            }
          });
        }

        const acc = totalDocs > 0 ? ((successfulDocs / totalDocs) * 100).toFixed(1) : '100';
        const time = timedDocs > 0 ? (totalTimeMs / timedDocs / 1000).toFixed(1) : '1.5';

        setStats({
          totalPatients: ptData?.total || 0,
          documentsProcessed: totalDocs,
          accuracy: `${acc}%`,
          avgTime: `${time}s`,
          loading: false
        });
      } catch {
        setStats(s => ({ ...s, loading: false }));
      }
    };

    loadData();
  }, []);

  return (
    <div className="page-content space-y-8 flex-1 h-full overflow-y-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-slate-200/80 dark:border-white/10 pb-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center border border-purple-500/30 shadow-[0_0_20px_rgba(168,85,247,0.2)]">
            <BarChart3 className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-wide">{t('an.title')}</h1>
            <p className="text-slate-400 text-sm mt-1">{t('an.subtitle')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select className="bg-white dark:bg-slate-800/50 border border-slate-300 dark:border-white/10 text-slate-800 dark:text-slate-300 text-sm rounded-lg px-4 py-2 outline-none focus:border-purple-500/50">
            <option>Last 7 Days</option>
            <option>Last 30 Days</option>
            <option>This Year</option>
          </select>
        </div>
      </div>

      {/* KPI Cards */}
      {stats.loading ? (
        <div className="flex justify-center py-10">
           <div className="w-6 h-6 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          <KpiCard title={t('an.totalConsult')} value={stats.totalPatients} change="+1" isPositive={true} icon={Users} color="cyan" />
          <KpiCard title={t('an.docsProcessed')} value={stats.documentsProcessed} change="+2" isPositive={true} icon={FileText} color="teal" />
          <KpiCard title={t('an.accuracy')} value={stats.accuracy} change="+0.1%" isPositive={true} icon={Activity} color="emerald" />
          <KpiCard title={t('an.avgTime')} value={stats.avgTime} change="-0.2s" isPositive={true} icon={TrendingUp} color="purple" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart Mock */}
        <div className="lg:col-span-2 bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 shadow-sm rounded-2xl shadow-2xl p-6 flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold text-slate-800 dark:text-slate-200">{t('an.volume')}</h2>
          </div>
          <div className="flex-1 flex items-end justify-between gap-2 h-64 pt-4 border-b border-slate-200/80 dark:border-white/10 relative">
            {/* Y-axis labels */}
            <div className="absolute left-0 top-0 bottom-0 w-8 flex flex-col justify-between text-xs text-slate-500 pb-6">
              <span>{Math.max(10, stats.documentsProcessed)}</span>
              <span>{Math.floor(Math.max(10, stats.documentsProcessed)/2)}</span>
              <span>0</span>
            </div>
            {/* Bars */}
            {[40, 70, 45, 90, 65, 80, 100].map((h, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2 z-10 ml-8">
                <div 
                  className="w-full max-w-[40px] bg-gradient-to-t from-purple-500/20 to-purple-400 rounded-t-md hover:to-purple-300 transition-colors cursor-pointer" 
                  style={{ height: `${stats.documentsProcessed > 0 ? h : 0}%` }}
                ></div>
                <span className="text-xs text-slate-400">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i]}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Secondary Info */}
        <div className="bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 shadow-sm rounded-2xl shadow-2xl p-6 flex flex-col">
          <h2 className="text-lg font-bold text-slate-800 dark:text-slate-200 mb-6">{t('an.types')}</h2>
          <div className="flex-1 flex flex-col justify-center gap-6">
            <DocTypeRow label={t('an.lab')} percentage={45} color="bg-cyan-400" />
            <DocTypeRow label={t('an.clinical')} percentage={30} color="bg-purple-400" />
            <DocTypeRow label={t('an.imaging')} percentage={15} color="bg-teal-400" />
            <DocTypeRow label={t('an.prescription')} percentage={10} color="bg-amber-400" />
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ title, value, change, isPositive, icon: Icon, color }: any) {
  const colorStyles: any = {
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    teal: 'text-teal-400 bg-teal-500/10 border-teal-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  };
  
  return (
    <div className="bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 shadow-sm rounded-2xl p-5 shadow-xl relative overflow-hidden group">
      <div className="flex justify-between items-start mb-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colorStyles[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className={`flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full ${isPositive ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
          {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
          {change}
        </div>
      </div>
      <div>
        <h3 className="text-slate-400 text-sm font-medium mb-1">{title}</h3>
        <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      </div>
      <div className={`absolute -bottom-6 -right-6 w-24 h-24 rounded-full blur-2xl opacity-20 group-hover:opacity-40 transition-opacity ${colorStyles[color].split(' ')[1]}`}></div>
    </div>
  );
}

function DocTypeRow({ label, percentage, color }: { label: string, percentage: number, color: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-2">
        <span className="text-slate-300 font-medium">{label}</span>
        <span className="text-slate-400">{percentage}%</span>
      </div>
      <div className="w-full bg-slate-800 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${percentage}%` }}></div>
      </div>
    </div>
  );
}
