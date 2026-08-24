'use client';

import React, { useEffect, useState } from 'react';
import UploadZone from '@/components/UploadZone';
import { FileText, Clock, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
import { ingestions } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { useLanguage } from '@/lib/i18n';
import DocumentModal from '@/components/DocumentModal';

export default function CaseFilesPage() {
  const [recentUploads, setRecentUploads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [quota, setQuota] = useState<{used_bytes: number, total_bytes: number} | null>(null);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const { refreshTrigger } = useAppStore();
  const { t } = useLanguage();
  const loadRecentUploads = async () => {
    try {
      const [data, quotaData] = await Promise.all([
        ingestions.list(5),
        ingestions.getQuota()
      ]);
      setRecentUploads(data || []);
      setQuota(quotaData);
    } catch (e) {
      console.error('Failed to load recent uploads or quota', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecentUploads();
  }, [refreshTrigger]);

  return (
    <div className="page-content space-y-6">
      <div className="flex items-center gap-4 border-b border-slate-200/80 dark:border-white/10 pb-6">
        <div className="w-12 h-12 rounded-xl bg-cyan-500/20 flex items-center justify-center border border-cyan-500/30">
          <FileText className="w-6 h-6 text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-wide">Case Files</h1>
          <p className="text-slate-400 text-sm mt-1">Manage and upload patient documents and FHIR records.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 shadow-sm rounded-2xl p-6 shadow-2xl">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,1)] animate-pulse" />
              Upload New File
            </h2>
            <UploadZone />
          </div>

          <div className="bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 shadow-sm rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200">Recent Uploads</h2>
              <button onClick={loadRecentUploads} className="p-1 text-slate-400 hover:text-slate-800 dark:text-slate-200 rounded">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              {loading ? (
                <div className="text-sm text-slate-500 text-center py-4">Loading...</div>
              ) : recentUploads.length === 0 ? (
                <div className="text-sm text-slate-500 text-center py-4">No recent uploads</div>
              ) : (
                recentUploads.map((file, idx) => {
                  return (
                    <div 
                      key={idx}
                      onClick={() => file.source_document_id && setPreviewDocId(file.source_document_id)}
                      className="flex items-center justify-between p-4 rounded-xl bg-slate-800/30 border border-white/5 hover:bg-slate-800/50 transition-colors cursor-pointer group"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-slate-400 group-hover:text-cyan-400 transition-colors" />
                        <div className="flex flex-col">
                          <span className="text-slate-800 dark:text-slate-200 font-medium text-sm group-hover:text-cyan-300 transition-colors">{file.source_document_id || 'Document'}</span>
                          <span className="text-xs text-slate-500">{new Date(file.received_at).toLocaleString()}</span>
                        </div>
                      </div>
                      <div className={`flex items-center gap-2 ${
                        file.status === 'completed' ? 'text-emerald-400' :
                        file.status === 'failed' ? 'text-red-400' : 'text-amber-400'
                      }`}>
                        {file.status === 'completed' ? <CheckCircle2 className="w-4 h-4" /> :
                         file.status === 'failed' ? <AlertCircle className="w-4 h-4" /> :
                         <Clock className="w-4 h-4" />}
                        <span className="text-xs uppercase tracking-widest font-semibold">{file.status}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-white dark:bg-[#112240] border border-slate-200/80 dark:border-teal-500/20 shadow-sm rounded-2xl p-6 shadow-2xl">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-widest mb-4">{t('cf.quota')}</h3>
            {quota ? (() => {
              const usedGB = (quota.used_bytes / (1024 * 1024 * 1024)).toFixed(2);
              const totalGB = (quota.total_bytes / (1024 * 1024 * 1024)).toFixed(0);
              const percentage = Math.min(100, Math.round((quota.used_bytes / quota.total_bytes) * 100));
              return (
                <>
                  <div className="w-full bg-slate-800 rounded-full h-2 mb-2">
                    <div className="bg-gradient-to-r from-cyan-500 to-teal-400 h-2 rounded-full shadow-[0_0_10px_rgba(34,211,238,0.5)] transition-all duration-500" style={{ width: `${percentage}%` }}></div>
                  </div>
                  <p className="text-xs text-slate-500 text-right">{percentage}% used ({usedGB}GB/{totalGB}GB)</p>
                </>
              );
            })() : (
              <div className="text-xs text-slate-500 text-center">Loading quota...</div>
            )}
          </div>
        </div>
      </div>

      <DocumentModal 
        isOpen={!!previewDocId} 
        onClose={() => setPreviewDocId(null)} 
        documentId={previewDocId} 
      />
    </div>
  );
}
