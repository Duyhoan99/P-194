'use client';

import { useEffect, useState } from 'react';
import { patients, ingestions } from '@/lib/api';
import { LayoutDashboard, Users, FileText, Activity, CheckCircle2, Clock, AlertCircle, Server, ArrowRight, Search } from 'lucide-react';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';
import DocumentModal from '@/components/DocumentModal';

interface DashboardStats {
  totalPatients: number;
  recentUploads: number;
  healthOk: boolean;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({ totalPatients: 0, recentUploads: 0, healthOk: false });
  const [patientList, setPatientList] = useState<any[]>([]);
  const [recentFiles, setRecentFiles] = useState<any[]>([]);
  const [allRecentFiles, setAllRecentFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [patientSearch, setPatientSearch] = useState('');
  const [uploadSearch, setUploadSearch] = useState('');
  const [showAllUploads, setShowAllUploads] = useState(false);
  const [showAllPatients, setShowAllPatients] = useState(false);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const { t, language } = useLanguage();

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [patientsRes, uploadsRes, healthRes] = await Promise.allSettled([
          patients.list({ page: 1, page_size: 5 }),
          ingestions.list(50), // Fetch more for local search
          fetch('/health').then(r => r.ok),
        ]);

        const ptData = patientsRes.status === 'fulfilled' ? patientsRes.value : null;
        const uploadsData = uploadsRes.status === 'fulfilled' ? uploadsRes.value : [];
        const healthOk = healthRes.status === 'fulfilled' ? healthRes.value : false;

        setStats({
          totalPatients: ptData?.total || 0,
          recentUploads: Array.isArray(uploadsData) ? uploadsData.length : 0,
          healthOk: !!healthOk,
        });
        setPatientList(ptData?.items || []);
        
        const uploadsArr = Array.isArray(uploadsData) ? uploadsData : [];
        setAllRecentFiles(uploadsArr);
        setRecentFiles(uploadsArr.slice(0, 4));
      } catch {
        // silently handle
      } finally {
        setLoading(false);
      }
    };

    loadDashboard();
  }, []);

  // Search effect for patients
  useEffect(() => {
    if (loading) return;
    const delayDebounceFn = setTimeout(() => {
      // Fetch more if showAllPatients is true, otherwise 5
      patients.list({ page: 1, page_size: showAllPatients ? 50 : 5, search: patientSearch }).then(res => {
        setPatientList(res.items || []);
      }).catch(console.error);
    }, 300);
    return () => clearTimeout(delayDebounceFn);
  }, [patientSearch, loading, showAllPatients]);

  // Search effect for uploads (local filtering)
  useEffect(() => {
    if (loading) return;
    if (!uploadSearch.trim()) {
      setRecentFiles(showAllUploads ? allRecentFiles : allRecentFiles.slice(0, 4));
      return;
    }
    const filtered = allRecentFiles.filter(f => 
      (f.source_document_id || '').toLowerCase().includes(uploadSearch.toLowerCase()) ||
      (f.status || '').toLowerCase().includes(uploadSearch.toLowerCase())
    );
    setRecentFiles(showAllUploads ? filtered : filtered.slice(0, 4));
  }, [uploadSearch, allRecentFiles, loading, showAllUploads]);

  return (
    <div className="page-content space-y-8">
      {/* Page Header */}
      <div className="flex items-center gap-4 border-b border-white/10 pb-6">
        <div className="w-12 h-12 rounded-2xl bg-teal-500/10 flex items-center justify-center border border-teal-500/30 shadow-[0_0_20px_rgba(20,184,166,0.25)]">
          <LayoutDashboard className="w-6 h-6 text-teal-300" />
        </div>
        <div>
          <h1 className="text-3xl font-light tracking-tight text-slate-100">{t('dash.title')}</h1>
          <p className="text-slate-400 text-sm mt-1">{t('dash.subtitle')}</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400">
          <div className="w-6 h-6 border-2 border-teal-500/30 border-t-teal-400 rounded-full animate-spin mr-3" />
          Loading dashboard...
        </div>
      ) : (
        <>
          {/* Stat Cards with Oura Serif Numbers */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <StatCard
              icon={Users}
              label={t('dash.totalPatients')}
              value={stats.totalPatients}
              color="teal"
            />
            <StatCard
              icon={FileText}
              label={t('dash.recentUploads')}
              value={stats.recentUploads}
              color="cyan"
            />
            <StatCard
              icon={Activity}
              label={t('dash.activeReviews')}
              value={stats.totalPatients > 0 ? Math.min(stats.totalPatients, 5) : 0}
              color="emerald"
            />
            <div className={`p-6 rounded-2xl oura-glass-card border shadow-xl ${
              stats.healthOk
                ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-950/20 border-rose-500/30 text-rose-300'
            }`}>
              <div className="flex items-center gap-3.5">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${
                  stats.healthOk ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300' : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
                }`}>
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{t('dash.systemStatus')}</p>
                  <p className="font-serif text-2xl font-light mt-0.5">
                    {stats.healthOk ? t('dash.operational') : t('dash.checking')}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Patients & Files */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Recent Patients */}
            <div className="oura-glass rounded-2xl p-6 border border-white/10 shadow-2xl flex flex-col min-h-[350px] max-h-[600px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <Users className="w-4 h-4 text-teal-400" /> {t('nav.recentPatients')}
                </h2>
                <button 
                  onClick={() => setShowAllPatients(!showAllPatients)} 
                  className="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1 cursor-pointer font-medium"
                >
                  {showAllPatients ? (language === 'vi' ? 'Thu gọn' : 'Show less') : t('dash.viewAll')} <ArrowRight className={`w-3 h-3 transition-transform ${showAllPatients ? '-rotate-90' : ''}`} />
                </button>
              </div>
              <div className="relative mb-4">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input 
                  type="text" 
                  placeholder={t('dash.searchPatients')} 
                  value={patientSearch}
                  onChange={(e) => setPatientSearch(e.target.value)}
                  className="w-full bg-[#0c121d] border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 transition-colors"
                />
              </div>
              <div className="space-y-2 flex-1 overflow-y-auto pr-1 chat-scrollbar">
                {patientList.length === 0 ? (
                  <p className="text-xs text-slate-500 text-center py-6">{t('dash.noPatients')}</p>
                ) : (
                  patientList.map((p) => (
                    <Link
                      key={p.patient_id}
                      href={`/patients/${p.patient_id}`}
                      className="flex items-center justify-between p-3.5 rounded-xl oura-glass-card hover:border-teal-500/40 transition-all group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-teal-500/15 flex items-center justify-center text-xs font-bold text-teal-300 border border-teal-500/30">
                          {p.pseudonym?.[0] || '?'}
                        </div>
                        <div>
                          <span className="text-xs font-medium text-slate-200 group-hover:text-teal-300 transition-colors">{p.pseudonym}</span>
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            {p.age} tuổi • {p.sex} {p.primary_condition ? `• ${p.primary_condition}` : ''}
                          </div>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-teal-300 transition-colors" />
                    </Link>
                  ))
                )}
              </div>
            </div>

            {/* Recent Files */}
            <div className="oura-glass rounded-2xl p-6 border border-white/10 shadow-2xl flex flex-col min-h-[350px] max-h-[600px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-cyan-400" /> {t('dash.recentUploads')}
                </h2>
                <button 
                  onClick={() => setShowAllUploads(!showAllUploads)} 
                  className="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1 cursor-pointer font-medium"
                >
                  {showAllUploads ? (language === 'vi' ? 'Thu gọn' : 'Show less') : t('dash.viewAll')} <ArrowRight className={`w-3 h-3 transition-transform ${showAllUploads ? '-rotate-90' : ''}`} />
                </button>
              </div>
              <div className="relative mb-4">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input 
                  type="text" 
                  placeholder={t('dash.searchDocs')} 
                  value={uploadSearch}
                  onChange={(e) => setUploadSearch(e.target.value)}
                  className="w-full bg-[#0c121d] border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 transition-colors"
                />
              </div>
              <div className="space-y-2 flex-1 overflow-y-auto pr-1 chat-scrollbar">
                {recentFiles.length === 0 ? (
                  <p className="text-xs text-slate-500 text-center py-6">{t('dash.noUploads')}</p>
                ) : (
                  recentFiles.map((f, idx) => {
                    return (
                      <div 
                        key={idx} 
                        onClick={() => f.source_document_id && setPreviewDocId(f.source_document_id)}
                        className="flex items-center justify-between p-3.5 rounded-xl oura-glass-card hover:border-teal-500/40 transition-all cursor-pointer group"
                      >
                        <div className="flex items-center gap-3">
                          <FileText className="w-4 h-4 text-slate-400 group-hover:text-teal-300 transition-colors" />
                          <div>
                            <span className="text-xs font-medium text-slate-200 max-w-[200px] truncate block group-hover:text-teal-300 transition-colors" title={f.source_document_id || 'Document'}>
                              {f.source_document_id || 'Document'}
                            </span>
                            <div className="text-[10px] text-slate-400 mt-0.5">
                              {f.received_at ? new Date(f.received_at).toLocaleString() : 'Unknown'}
                            </div>
                          </div>
                        </div>
                        <div className={`flex items-center gap-1 text-[11px] font-semibold uppercase ${
                          f.status === 'completed' ? 'text-emerald-400' :
                          f.status === 'failed' ? 'text-rose-400' : 'text-amber-400'
                        }`}>
                          {f.status === 'completed' ? <CheckCircle2 className="w-3.5 h-3.5" /> :
                           f.status === 'failed' ? <AlertCircle className="w-3.5 h-3.5" /> :
                           <Clock className="w-3.5 h-3.5" />}
                          {f.status}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </>
      )}

      <DocumentModal 
        isOpen={!!previewDocId} 
        onClose={() => setPreviewDocId(null)} 
        documentId={previewDocId} 
      />
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    teal: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
    cyan: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  };

  return (
    <div className="p-6 rounded-2xl oura-glass-card border border-white/10 shadow-xl space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{label}</span>
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center border ${colorMap[color] || colorMap.teal}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <p className="font-serif text-4xl font-light text-slate-100">{value}</p>
    </div>
  );
}

