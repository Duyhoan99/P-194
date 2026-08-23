'use client';

import { useEffect, useState } from 'react';
import { patients, ingestions } from '@/lib/api';
import { LayoutDashboard, Users, FileText, Activity, CheckCircle2, Clock, AlertCircle, Server, ArrowRight, Search, UploadCloud } from 'lucide-react';
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
          ingestions.list(50),
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
    <div className="page-content space-y-7">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b pb-5" style={{ borderColor: 'var(--border-card)' }}>
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center border shadow-sm" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
            <LayoutDashboard className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">{t('dash.title')}</h1>
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>{t('dash.subtitle')}</p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24" style={{ color: 'var(--text-muted)' }}>
          <div className="w-6 h-6 border-2 rounded-full animate-spin mr-3" style={{ borderColor: 'var(--accent-teal-border)', borderTopColor: 'var(--accent-teal)' }} />
          Loading dashboard...
        </div>
      ) : (
        <>
          {/* Stat Cards */}
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

            {/* System Status Card */}
            <div className="clinical-card p-6 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                  {t('dash.systemStatus')}
                </span>
                <div className="w-9 h-9 rounded-xl flex items-center justify-center border" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
                  <Server className="w-4 h-4" />
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">
                  {stats.healthOk ? t('dash.operational') : t('dash.checking')}
                </span>
              </div>
            </div>
          </div>

          {/* Recent Patients & Files */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            
            {/* Recent Patients */}
            <div className="clinical-card p-6 flex flex-col min-h-[360px] max-h-[600px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center border" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
                    <Users className="w-3.5 h-3.5" />
                  </div>
                  <span>{t('nav.recentPatients')}</span>
                </h2>
                <button 
                  onClick={() => setShowAllPatients(!showAllPatients)} 
                  className="text-xs flex items-center gap-1 cursor-pointer font-bold transition-colors"
                  style={{ color: 'var(--accent-teal)' }}
                >
                  {showAllPatients ? (language === 'vi' ? 'Thu gọn' : 'Show less') : t('dash.viewAll')} 
                  <ArrowRight className={`w-3.5 h-3.5 transition-transform ${showAllPatients ? '-rotate-90' : ''}`} />
                </button>
              </div>

              {/* Search input */}
              <div className="relative mb-4">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
                <input 
                  type="text" 
                  placeholder={t('dash.searchPatients')} 
                  value={patientSearch}
                  onChange={(e) => setPatientSearch(e.target.value)}
                  className="clinical-input w-full pl-10 pr-4 py-2.5 text-xs font-medium"
                />
              </div>

              <div className="space-y-2 flex-1 overflow-y-auto pr-1 chat-scrollbar">
                {patientList.length === 0 ? (
                  <div className="text-center py-10 text-xs" style={{ color: 'var(--text-muted)' }}>
                    <Users className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    {t('dash.noPatients')}
                  </div>
                ) : (
                  patientList.map((p) => (
                    <Link
                      key={p.patient_id}
                      href={`/patients/${p.patient_id}`}
                      className="clinical-subcard flex items-center justify-between p-3.5 group shadow-none hover:shadow-sm"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-extrabold border shrink-0" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
                          {p.pseudonym?.[0] || '?'}
                        </div>
                        <div>
                          <span className="text-xs font-bold block group-hover:text-teal-600 dark:group-hover:text-teal-300 transition-colors">
                            {p.pseudonym}
                          </span>
                          <div className="text-[11px] mt-0.5 font-medium" style={{ color: 'var(--text-muted)' }}>
                            {p.age} tuổi • {p.sex} {p.primary_condition ? `• ${p.primary_condition}` : ''}
                          </div>
                        </div>
                      </div>
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center border group-hover:bg-teal-600 group-hover:text-white transition-all" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--text-muted)' }}>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </div>
                    </Link>
                  ))
                )}
              </div>
            </div>

            {/* Recent Files */}
            <div className="clinical-card p-6 flex flex-col min-h-[360px] max-h-[600px]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center border" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
                    <FileText className="w-3.5 h-3.5" />
                  </div>
                  <span>{t('dash.recentUploads')}</span>
                </h2>
                <button 
                  onClick={() => setShowAllUploads(!showAllUploads)} 
                  className="text-xs flex items-center gap-1 cursor-pointer font-bold transition-colors"
                  style={{ color: 'var(--accent-teal)' }}
                >
                  {showAllUploads ? (language === 'vi' ? 'Thu gọn' : 'Show less') : t('dash.viewAll')} 
                  <ArrowRight className={`w-3.5 h-3.5 transition-transform ${showAllUploads ? '-rotate-90' : ''}`} />
                </button>
              </div>

              {/* Search input */}
              <div className="relative mb-4">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
                <input 
                  type="text" 
                  placeholder={t('dash.searchDocs')} 
                  value={uploadSearch}
                  onChange={(e) => setUploadSearch(e.target.value)}
                  className="clinical-input w-full pl-10 pr-4 py-2.5 text-xs font-medium"
                />
              </div>

              <div className="space-y-2 flex-1 overflow-y-auto pr-1 chat-scrollbar">
                {recentFiles.length === 0 ? (
                  <div className="text-center py-12 text-xs" style={{ color: 'var(--text-muted)' }}>
                    <UploadCloud className="w-9 h-9 mx-auto mb-2 opacity-35" />
                    <p className="font-medium">{t('dash.noUploads')}</p>
                    <Link href="/case-files" className="inline-block mt-2 font-semibold hover:underline" style={{ color: 'var(--accent-teal)' }}>
                      Tải lên tài liệu PDF mới →
                    </Link>
                  </div>
                ) : (
                  recentFiles.map((f, idx) => (
                    <div 
                      key={idx} 
                      onClick={() => f.source_document_id && setPreviewDocId(f.source_document_id)}
                      className="clinical-subcard flex items-center justify-between p-3.5 cursor-pointer group shadow-none hover:shadow-sm"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center border shrink-0" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--text-muted)' }}>
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <span className="text-xs font-bold max-w-[200px] truncate block group-hover:text-teal-600 dark:group-hover:text-teal-300 transition-colors" title={f.source_document_id || 'Document'}>
                            {f.source_document_id || 'Document'}
                          </span>
                          <div className="text-[11px] mt-0.5 font-medium" style={{ color: 'var(--text-muted)' }}>
                            {f.received_at ? new Date(f.received_at).toLocaleString() : 'Unknown'}
                          </div>
                        </div>
                      </div>
                      <div className={`flex items-center gap-1.5 text-[11px] font-bold uppercase px-2.5 py-1 rounded-full border ${
                        f.status === 'completed' ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800' :
                        f.status === 'failed' ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800' : 
                        'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800'
                      }`}>
                        {f.status === 'completed' ? <CheckCircle2 className="w-3.5 h-3.5" /> :
                         f.status === 'failed' ? <AlertCircle className="w-3.5 h-3.5" /> :
                         <Clock className="w-3.5 h-3.5" />}
                        <span>{f.status}</span>
                      </div>
                    </div>
                  ))
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
  return (
    <div className="clinical-card p-6 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
          {label}
        </span>
        <div className="w-9 h-9 rounded-xl flex items-center justify-center border" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <p className="text-3xl sm:text-4xl font-extrabold tracking-tight">
        {value}
      </p>
    </div>
  );
}
