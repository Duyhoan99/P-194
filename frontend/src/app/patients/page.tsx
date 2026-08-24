'use client';

import { useCallback, useEffect, useState } from 'react';
import { patients } from '@/lib/api';
import { Users, Search, ArrowRight, UserPlus, Activity, Calendar, Trash2, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';

export default function PatientsLandingPage() {
  const [patientList, setPatientList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState<string | null>(null);
  const { t } = useLanguage();

  const loadPatients = useCallback(() => {
    setLoading(true);
    patients.list({ page: 1, page_size: 50, search }).then(res => {
      setPatientList(res.items || []);
    }).catch(console.error).finally(() => setLoading(false));
  }, [search]);

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      loadPatients();
    }, 300);
    return () => clearTimeout(delayDebounceFn);
  }, [loadPatients]);

  const handleDelete = async (patientId: string) => {
    setDeletingId(patientId);
    try {
      await patients.delete(patientId);
      setShowConfirm(null);
      loadPatients();
    } catch (err) {
      console.error(err);
      alert(t('pt.deleteError'));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="page-content space-y-7 flex-1 h-full overflow-y-auto chat-scrollbar">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-slate-200/80 dark:border-teal-500/20 pb-5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-teal-500/10 dark:bg-teal-500/15 flex items-center justify-center border border-teal-500/30 text-teal-600 dark:text-teal-300 shadow-sm">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">{t('pt.title')}</h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5">{t('pt.subtitle')}</p>
          </div>
        </div>

        <Link
          href="/case-files"
          className="flex items-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-xs font-bold shadow-md shadow-teal-900/30 transition-all"
        >
          <UserPlus className="w-4 h-4" />
          <span>Tải lên hồ sơ bệnh nhân mới</span>
        </Link>
      </div>

      {/* Search and Problem-Oriented Filters */}
      <div className="space-y-3.5 bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 p-5 rounded-2xl shadow-sm">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder={t('pt.search')} 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-50 dark:bg-[#0d1b30] border border-slate-200 dark:border-teal-500/20 rounded-xl pl-11 pr-4 py-3 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:bg-white dark:focus:bg-[#162c4e] focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all font-medium"
          />
        </div>

        {/* Problem-Oriented Specialty Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100 dark:border-white/5">
          <span className="text-xs text-slate-500 dark:text-slate-400 font-bold mr-1">Bộ lọc lâm sàng:</span>
          {[
            { label: 'Tất cả', query: '' },
            { label: '🩸 Đái tháo đường T2', query: 'diabetes' },
            { label: '🫀 Tăng huyết áp', query: 'hypertension' },
            { label: '🧪 Bệnh thận mạn CKD', query: 'kidney' },
            { label: '⚠️ Cần rà soát gấp', query: 'alert' }
          ].map((chip, idx) => (
            <button
              key={idx}
              onClick={() => setSearch(chip.query)}
              className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
                search === chip.query
                  ? 'bg-teal-600 text-white shadow-sm shadow-teal-600/25 dark:bg-teal-500/20 dark:text-teal-200 dark:border dark:border-teal-500/40'
                  : 'bg-slate-100 hover:bg-slate-200/80 text-slate-600 dark:bg-white/5 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {/* Patient List */}
      <div className="bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 rounded-2xl shadow-sm p-6 min-h-[400px]">
        {loading && patientList.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-slate-400">
            <div className="w-6 h-6 border-2 border-teal-500/30 border-t-teal-500 rounded-full animate-spin mr-3" />
          </div>
        ) : patientList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <UserPlus className="w-12 h-12 text-slate-400 mb-4 opacity-40" />
            <p className="text-base font-bold text-slate-700 dark:text-slate-300">{t('pt.notFound')}</p>
            <p className="text-xs text-slate-500 mt-1">{t('pt.trySearch')}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {patientList.map((p) => (
              <Link
                key={p.patient_id}
                href={`/patients/${p.patient_id}`}
                className="flex flex-col p-5 sm:p-6 rounded-2xl bg-slate-50/70 hover:bg-teal-50/60 dark:bg-white/[0.03] dark:hover:bg-white/[0.08] border border-slate-200/70 hover:border-teal-300 dark:border-white/5 dark:hover:border-teal-500/40 transition-all group shadow-none hover:shadow-md relative overflow-hidden"
              >
                <div className="flex items-start justify-between mb-4 relative z-10">
                  <div className="flex items-center gap-3.5">
                    <div className="w-11 h-11 rounded-2xl bg-teal-100 text-teal-800 dark:bg-teal-500/15 dark:text-teal-300 flex items-center justify-center text-sm font-extrabold border border-teal-200 dark:border-teal-500/30 shadow-sm shrink-0">
                      {p.pseudonym?.[0] || '?'}
                    </div>
                    <div>
                      <h3 className="text-sm text-slate-900 dark:text-slate-100 font-extrabold group-hover:text-teal-600 dark:group-hover:text-teal-300 transition-colors">{p.pseudonym}</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">{p.patient_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowConfirm(p.patient_id); }}
                      className="p-1.5 rounded-lg bg-white dark:bg-slate-800/80 border border-slate-200/60 dark:border-transparent hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10 dark:hover:text-rose-400 text-slate-400 transition-all opacity-0 group-hover:opacity-100"
                      title={t('pt.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <div className="w-7 h-7 rounded-lg bg-white dark:bg-white/5 flex items-center justify-center border border-slate-200/60 dark:border-teal-500/20 group-hover:border-teal-300 group-hover:bg-teal-600 group-hover:text-white transition-all text-slate-400">
                      <ArrowRight className="w-3.5 h-3.5" />
                    </div>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-3 mt-auto pt-3.5 border-t border-slate-200/60 dark:border-white/5 relative z-10 text-xs font-medium">
                  <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                    <Calendar className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                    <span>{p.age} tuổi • {p.sex}</span>
                  </div>
                  {p.primary_condition && (
                    <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                      <Activity className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                      <span className="truncate block max-w-[120px]" title={p.primary_condition}>{p.primary_condition}</span>
                    </div>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-teal-500/20 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6">
              <div className="w-12 h-12 rounded-2xl bg-rose-50 dark:bg-rose-500/20 flex items-center justify-center mb-4 border border-rose-200 dark:border-red-500/30">
                <AlertTriangle className="w-6 h-6 text-rose-600 dark:text-red-400" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">{t('pt.deleteConfirm')}</h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">
                {t('pt.deleteDesc')}
              </p>
            </div>
            <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-t border-slate-100 dark:border-white/5 flex items-center justify-end gap-3">
              <button
                onClick={() => setShowConfirm(null)}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:text-white dark:hover:bg-slate-700 transition-colors"
                disabled={deletingId !== null}
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => handleDelete(showConfirm)}
                disabled={deletingId === showConfirm}
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-rose-600 hover:bg-rose-700 text-white shadow-lg shadow-rose-600/20 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deletingId === showConfirm ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                {t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
