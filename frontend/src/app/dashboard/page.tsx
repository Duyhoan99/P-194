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
      <div className="flex items-center gap-4 border-b border-white/5 pb-6">
        <div className="w-12 h-12 rounded-xl bg-cyan-500/20 flex items-center justify-center border border-cyan-500/30 shadow-[0_0_20px_rgba(34,211,238,0.2)]">
          <LayoutDashboard className="w-6 h-6 text-cyan-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-slate-100 tracking-wide">{t('dash.title')}</h1>
          <p className="text-slate-400 text-sm mt-1">{t('dash.subtitle')}</p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500">
          <div className="w-6 h-6 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mr-3" />
          Loading dashboard...
        </div>
      ) : (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={Users}
              label={t('dash.totalPatients')}
              value={stats.totalPatients}
              color="cyan"
            />
            <StatCard
              icon={FileText}
              label={t('dash.recentUploads')}
              value={stats.recentUploads}
              color="teal"
            />
            <StatCard
              icon={Activity}
              label={t('dash.activeReviews')}
              value={stats.totalPatients > 0 ? Math.min(stats.totalPatients, 5) : 0} // Mock active reviews based on total
              color="purple"
            />
            <div className={`p-5 rounded-2xl border backdrop-blur-xl shadow-xl ${
              stats.healthOk
                ? 'bg-emerald-500/5 border-emerald-500/20'
                : 'bg-red-500/5 border-red-500/20'
            }`}>
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  stats.healthOk ? 'bg-emerald-500/10' : 'bg-red-500/10'
                }`}>
                  <Server className={`w-5 h-5 ${stats.healthOk ? 'text-emerald-400' : 'text-red-400'}`} />
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{t('dash.systemStatus')}</p>
                  <p className={`text-lg font-bold ${stats.healthOk ? 'text-emerald-400' : 'text-red-400'}`}>
                    {stats.healthOk ? t('dash.operational') : t('dash.checking')}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Patients & Files */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Recent Patients */}
            <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6 shadow-2xl flex flex-col min-h-[350px] max-h-[600px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
                  <Users className="w-4 h-4 text-cyan-400" /> {t('nav.recentPatients')}
                </h2>
                <button 
                  onClick={() => setShowAllPatients(!showAllPatients)} 
                  className="text-xs text-cyan-500 hover:text-cyan-400 flex items-center gap-1 cursor-pointer"
                >
                  {showAllPatients ? (language === 'vi' ? 'Thu gọn' : 'Show less') : t('dash.viewAll')} <ArrowRight className={`w-3 h-3 transition-transform ${showAllPatients ? '-rotate-90' : ''}`} />
                </button>
              </div>
              <div className="relative mb-4">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input 
                  type="text" 
                  placeholder={t('dash.searchPatients')} 
                  value={patientSearch}
                  onChange={(e) => setPatientSearch(e.target.value)}
                  className="w-full bg-slate-800/50 border border-white/10 rounded-xl pl-9 pr-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors"
                />
              </div>
              <div className="space-y-2 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                {patientList.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-4">{t('dash.noPatients')}</p>
                ) : (
                  patientList.map((p) => (
                    <Link
                      key={p.patient_id}
                      href={`/patients/${p.patient_id}`}
                      className="flex items-center justify-between p-3 rounded-xl bg-slate-800/20 border border-white/[0.03] hover:bg-slate-800/40 transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs font-bold text-cyan-400 border border-slate-700">
                          {p.pseudonym?.[0] || '?'}
                        </div>
                        <div>
                          <span className="text-sm text-slate-200 font-medium group-hover:text-cyan-300 transition-colors">{p.pseudonym}</span>
                          <div className="text-[10px] text-slate-500 mt-0.5">
                            {p.age}y • {p.sex} {p.primary_condition ? `• ${p.primary_condition}` : ''}
                          </div>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 transition-colors" />
                    </Link>
                  ))
                )}
              </div>
            </div>

            {/* Recent Files */}
            <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6 shadow-2xl flex flex-col min-h-[350px] max-h-[600px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-slate-200 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-teal-400" /> {t('dash.recentUploads')}
                </h2>
                <button 
                  onClick={() => setShowAllUploads(!showAllUploads)} 
                  className="text-xs text-cyan-500 hover:text-cyan-400 flex items-center gap-1 cursor-pointer"
                >
                  {showAllUploads ? (language === 'vi' ? 'Thu gọn' : 'Show less') : t('dash.viewAll')} <ArrowRight className={`w-3 h-3 transition-transform ${showAllUploads ? '-rotate-90' : ''}`} />
                </button>
              </div>
              <div className="relative mb-4">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input 
                  type="text" 
                  placeholder={t('dash.searchDocs')} 
                  value={uploadSearch}
                  onChange={(e) => setUploadSearch(e.target.value)}
                  className="w-full bg-slate-800/50 border border-white/10 rounded-xl pl-9 pr-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500/50 transition-colors"
                />
              </div>
              <div className="space-y-2 flex-1 overflow-y-auto pr-2 custom-scrollbar">
                {recentFiles.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-4">{t('dash.noUploads')}</p>
                ) : (
                  recentFiles.map((f, idx) => {
                    return (
                      <div 
                        key={idx} 
                        onClick={() => f.source_document_id && setPreviewDocId(f.source_document_id)}
                        className="flex items-center justify-between p-3 rounded-xl bg-slate-800/20 border border-white/[0.03] hover:bg-slate-800/40 transition-colors cursor-pointer group"
                      >
                        <div className="flex items-center gap-3">
                          <FileText className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                          <div>
                            <span className="text-sm text-slate-300 max-w-[200px] truncate block group-hover:text-cyan-300 transition-colors" title={f.source_document_id || 'Document'}>
                              {f.source_document_id || 'Document'}
                            </span>
                            <div className="text-[10px] text-slate-500 mt-0.5">
                              {f.received_at ? new Date(f.received_at).toLocaleString() : 'Unknown'}
                            </div>
                          </div>
                        </div>
                        <div className={`flex items-center gap-1 text-xs font-bold uppercase ${
                          f.status === 'completed' ? 'text-emerald-400' :
                          f.status === 'failed' ? 'text-red-400' : 'text-amber-400'
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
    cyan: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20 shadow-cyan-900/10',
    teal: 'bg-teal-500/10 text-teal-400 border-teal-500/20 shadow-teal-900/10',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20 shadow-purple-900/10',
  };

  return (
    <div className={`p-5 rounded-2xl border backdrop-blur-xl shadow-xl bg-slate-900/40 border-white/5`}>
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colorMap[color]?.split(' ').slice(0, 1).join(' ') || 'bg-cyan-500/10'}`}>
          <Icon className={`w-5 h-5 ${colorMap[color]?.split(' ')[1] || 'text-cyan-400'}`} />
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
          <p className="text-2xl font-bold text-slate-100">{value}</p>
        </div>
      </div>
    </div>
  );
}

