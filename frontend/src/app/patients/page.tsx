'use client';

import { useEffect, useState } from 'react';
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

  const loadPatients = () => {
    setLoading(true);
    patients.list({ page: 1, page_size: 50, search }).then(res => {
      setPatientList(res.items || []);
    }).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      loadPatients();
    }, 300);
    return () => clearTimeout(delayDebounceFn);
  }, [search]);

  const handleDelete = async (patientId: string) => {
    setDeletingId(patientId);
    try {
      await patients.delete(patientId);
      setShowConfirm(null);
      loadPatients();
      // Optional: show a toast notification here
    } catch (err) {
      console.error(err);
      alert(t('pt.deleteError'));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="page-content space-y-8 flex-1 h-full overflow-y-auto chat-scrollbar">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-teal-500/10 flex items-center justify-center border border-teal-500/30 shadow-[0_0_20px_rgba(20,184,166,0.25)]">
            <Users className="w-6 h-6 text-teal-300" />
          </div>
          <div>
            <h1 className="text-3xl font-light tracking-tight text-slate-100">{t('pt.title')}</h1>
            <p className="text-slate-400 text-sm mt-1">{t('pt.subtitle')}</p>
          </div>
        </div>
      </div>

      {/* Search and Problem-Oriented Filters */}
      <div className="space-y-3 oura-glass border border-white/10 p-5 rounded-2xl shadow-xl">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder={t('pt.search')} 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[#0c121d] border border-white/10 rounded-xl pl-11 pr-4 py-3 text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 transition-colors"
          />
        </div>

        {/* Problem-Oriented Specialty Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/5">
          <span className="text-xs text-slate-400 font-medium mr-1">Bộ lọc lâm sàng:</span>
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
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all oura-pill ${
                search === chip.query
                  ? 'bg-teal-500/20 text-teal-200 border-teal-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {/* Patient List */}
      <div className="oura-glass border border-white/10 rounded-2xl shadow-2xl p-6 min-h-[400px]">
        {loading && patientList.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-slate-400">
            <div className="w-6 h-6 border-2 border-teal-500/30 border-t-teal-400 rounded-full animate-spin mr-3" />
          </div>
        ) : patientList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <UserPlus className="w-12 h-12 text-slate-600 mb-4" />
            <p className="text-lg font-medium text-slate-300">{t('pt.notFound')}</p>
            <p className="text-sm mt-1">{t('pt.trySearch')}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {patientList.map((p) => (
              <Link
                key={p.patient_id}
                href={`/patients/${p.patient_id}`}
                className="flex flex-col p-6 rounded-2xl oura-glass-card hover:border-teal-500/40 transition-all group shadow-lg relative overflow-hidden"
              >
                <div className="flex items-start justify-between mb-4 relative z-10">
                  <div className="flex items-center gap-3.5">
                    <div className="w-12 h-12 rounded-full bg-teal-500/15 flex items-center justify-center text-base font-bold text-teal-300 border border-teal-500/30 shadow-sm">
                      {p.pseudonym?.[0] || '?'}
                    </div>
                    <div>
                      <h3 className="text-sm text-slate-100 font-semibold group-hover:text-teal-300 transition-colors">{p.pseudonym}</h3>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">{p.patient_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowConfirm(p.patient_id); }}
                      className="p-1.5 rounded-lg bg-slate-800/80 border border-transparent hover:border-rose-500/50 hover:bg-rose-500/10 hover:text-rose-400 text-slate-500 transition-all opacity-0 group-hover:opacity-100"
                      title={t('pt.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-teal-300 transition-colors" />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-3 mt-auto pt-4 border-t border-white/5 relative z-10 text-xs">
                  <div className="flex items-center gap-2 text-slate-400">
                    <Calendar className="w-3.5 h-3.5 text-teal-400" />
                    <span>{p.age} tuổi • {p.sex}</span>
                  </div>
                  {p.primary_condition && (
                    <div className="flex items-center gap-2 text-slate-400">
                      <Activity className="w-3.5 h-3.5 text-cyan-400" />
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
          <div className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6">
              <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center mb-4 border border-red-500/30">
                <AlertTriangle className="w-6 h-6 text-red-400" />
              </div>
              <h3 className="text-xl font-bold text-slate-100 mb-2">{t('pt.deleteConfirm')}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                {t('pt.deleteDesc')}
              </p>
            </div>
            <div className="bg-slate-800/50 p-4 border-t border-white/5 flex items-center justify-end gap-3">
              <button
                onClick={() => setShowConfirm(null)}
                className="px-4 py-2 rounded-xl text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
                disabled={deletingId !== null}
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => handleDelete(showConfirm)}
                disabled={deletingId === showConfirm}
                className="px-4 py-2 rounded-xl text-sm font-medium bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
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
