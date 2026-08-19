'use client';

import { useEffect, useRef, useState } from 'react';
import { ingestions, patients } from '@/lib/api';
import { AlertCircle, CheckCircle2, FileText, Loader2, UploadCloud, UserCheck, X } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';

type UploadStatus = 'queued' | 'uploading' | 'processing' | 'completed' | 'completed_with_warnings' | 'failed';

type UploadItem = {
  id: string;
  file: File;
  status: UploadStatus;
  progress: number;
  batchId?: string;
  error?: string;
};

const terminalStatuses = new Set<UploadStatus>(['completed', 'completed_with_warnings', 'failed']);
const sleep = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function fileId(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

export default function UploadZone({ onUploadComplete }: { onUploadComplete?: () => void }) {
  const { selectedPatient, triggerRefresh } = useAppStore();
  const contextPatientId = selectedPatient?.patient_id || '';
  const [patientList, setPatientList] = useState<any[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string>(contextPatientId || 'auto');
  const [newPatientName, setNewPatientName] = useState('');
  const [items, setItems] = useState<UploadItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    patients.list({ page_size: 50 }).then((res) => {
      if (res?.items) {
        setPatientList(res.items);
      }
    }).catch(() => {});
  }, []);

  const updateItem = (id: string, patch: Partial<UploadItem>) => {
    setItems((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  };

  const addFiles = (files: File[]) => {
    setItems((current) => {
      const known = new Set(current.map((item) => item.id));
      const additions = files
        .filter((file) => !known.has(fileId(file)))
        .map((file) => ({ id: fileId(file), file, status: 'queued' as const, progress: 0 }));
      return [...current, ...additions];
    });
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files || []));
    event.target.value = '';
  };

  const pollStatus = async (itemId: string, batchId: string) => {
    for (let attempt = 1; attempt <= 30; attempt += 1) {
      await sleep(2000);
      const result = await ingestions.getStatus(batchId);
      const status = result.status as UploadStatus;
      updateItem(itemId, { status, progress: Math.min(90, attempt * 9) });
      if (terminalStatuses.has(status)) return result;
    }
    throw new Error('Timed out while processing document.');
  };

  const handleUpload = async () => {
    const queued = items.filter((item) => item.status === 'queued' || item.status === 'failed');
    if (!queued.length || isUploading) return;

    setIsUploading(true);
    let targetPid = contextPatientId || (selectedTarget !== 'auto' && selectedTarget !== 'new' ? selectedTarget : undefined);
    let targetName = selectedTarget === 'new' ? newPatientName : undefined;

    try {
      for (const item of queued) {
        updateItem(item.id, { status: 'uploading', progress: 10, error: undefined });
        try {
          const result = await ingestions.upload(
            item.file,
            targetPid,
            'auto',
            targetName,
          );
          targetPid = targetPid || result.patient_id || '';
          if (!targetPid) throw new Error('Backend did not return the patient created for this upload.');

          const initialStatus = result.status as UploadStatus;
          updateItem(item.id, {
            batchId: result.batch_id,
            status: terminalStatuses.has(initialStatus) ? initialStatus : 'processing',
            progress: terminalStatuses.has(initialStatus) ? 100 : 25,
          });
          if (!terminalStatuses.has(initialStatus)) {
            const finalResult = await pollStatus(item.id, result.batch_id);
            updateItem(item.id, { status: finalResult.status, progress: 100 });
          }
        } catch (error) {
          updateItem(item.id, {
            status: 'failed',
            progress: 100,
            error: error instanceof Error ? error.message : 'Failed to process document.',
          });
          if (!targetPid && !contextPatientId) break;
        }
      }
    } finally {
      setIsUploading(false);
      triggerRefresh();
      onUploadComplete?.();
    }
  };

  const pendingCount = items.filter((item) => item.status === 'queued' || item.status === 'failed').length;

  return (
    <div className="bg-slate-900/40 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-6 shadow-2xl shadow-cyan-900/10">
      <h3 className="text-sm font-bold tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-teal-300 mb-4 flex items-center gap-2">
        <UploadCloud className="w-4 h-4 text-cyan-400" aria-hidden="true" /> Upload Documents
      </h3>

      <div
        className={`border-2 border-dashed rounded-xl p-6 transition-colors bg-slate-950/40 ${
          isDragging ? 'border-cyan-400 bg-cyan-950/30' : 'border-cyan-800/50 hover:border-cyan-400/50'
        }`}
        onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => { event.preventDefault(); setIsDragging(false); }}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          if (!isUploading) addFiles(Array.from(event.dataTransfer.files));
        }}
      >
        {!contextPatientId && (
          <div className="w-full mb-6 space-y-3">
            <div>
              <label htmlFor="target-patient" className="block text-left text-xs font-semibold text-cyan-400 uppercase tracking-widest mb-2">
                Hồ sơ bệnh nhân đích
              </label>
              <select
                id="target-patient"
                value={selectedTarget}
                disabled={isUploading}
                onChange={(e) => setSelectedTarget(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-cyan-500 disabled:opacity-50 transition-colors"
              >
                <option value="auto">✨ Tự động nhận diện từ tài liệu (AI Auto-detect)</option>
                {patientList.map((p) => (
                  <option key={p.patient_id} value={p.patient_id}>
                    {p.pseudonym} ({p.patient_id})
                  </option>
                ))}
                <option value="new">➕ Tạo bệnh nhân mới...</option>
              </select>
            </div>

            {selectedTarget === 'new' && (
              <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
                <label htmlFor="new-patient-name" className="block text-left text-xs font-semibold text-teal-400 uppercase tracking-widest mb-2">
                  Tên bệnh nhân mới
                </label>
                <input
                  id="new-patient-name"
                  type="text"
                  value={newPatientName}
                  disabled={isUploading}
                  onChange={(event) => setNewPatientName(event.target.value)}
                  placeholder="VD: Nguyễn Văn A..."
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-cyan-500 disabled:opacity-50 transition-colors"
                />
              </motion.div>
            )}
          </div>
        )}

        {contextPatientId && (
          <p className="mb-4 text-xs text-slate-400 flex items-center gap-1.5">
            <UserCheck className="w-4 h-4 text-cyan-400" />
            Tất cả tệp sẽ được thêm vào bệnh nhân <span className="font-semibold text-cyan-300">{contextPatientId}</span>.
          </p>
        )}


        <input
          id="file-upload"
          type="file"
          multiple
          accept=".pdf,application/pdf,.json,application/json,image/png,image/jpeg,.png,.jpg,.jpeg"
          className="hidden"
          ref={fileInputRef}
          onChange={handleFileChange}
          disabled={isUploading}
        />

        <button
          type="button"
          disabled={isUploading}
          onClick={() => fileInputRef.current?.click()}
          className="w-full min-h-32 flex flex-col items-center justify-center rounded-lg hover:bg-cyan-950/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:opacity-50 transition-colors"
          aria-label="Chọn nhiều tài liệu để tải lên"
        >
          <span className="w-14 h-14 rounded-full bg-cyan-950/80 flex items-center justify-center mb-3 border border-cyan-800/50 shadow-inner shadow-cyan-500/20">
            <UploadCloud className="w-6 h-6 text-cyan-400" aria-hidden="true" />
          </span>
          <span className="text-sm font-semibold text-slate-200">Chọn nhiều tệp hoặc kéo thả vào đây</span>
          <span className="text-xs text-slate-400 mt-2">PDF, PNG/JPG hoặc FHIR R4 JSON</span>
        </button>
      </div>

      {items.length > 0 && (
        <div className="mt-4 space-y-3" aria-live="polite" aria-label="Danh sách tài liệu tải lên">
          {items.map((item) => (
            <div key={item.id} className="p-3 bg-slate-950/50 rounded-lg border border-slate-800">
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4 shrink-0 text-slate-400" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-200">{item.file.name}</p>
                  <p className="text-xs text-slate-500">{(item.file.size / 1024).toFixed(1)} KB</p>
                </div>
                <span className={`text-xs font-medium ${
                  item.status === 'failed' ? 'text-red-400' :
                  item.status.includes('completed') ? 'text-emerald-400' : 'text-cyan-400'
                }`}>
                  {item.status}
                </span>
                {item.status === 'queued' && !isUploading && (
                  <button
                    type="button"
                    onClick={() => setItems((current) => current.filter((candidate) => candidate.id !== item.id))}
                    className="min-w-11 min-h-11 inline-flex items-center justify-center rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                    aria-label={`Xóa ${item.file.name}`}
                  >
                    <X className="w-4 h-4" aria-hidden="true" />
                  </button>
                )}
              </div>

              {item.status !== 'queued' && (
                <div className="mt-2">
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <motion.div
                      className={`h-1.5 rounded-full ${item.status === 'failed' ? 'bg-red-500' : 'bg-gradient-to-r from-cyan-500 to-teal-400'}`}
                      initial={false}
                      animate={{ width: `${item.progress}%` }}
                      transition={{ duration: 0.25 }}
                    />
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
                    {item.status === 'uploading' || item.status === 'processing' ? (
                      <Loader2 className="w-4 h-4 text-teal-400 animate-spin" aria-hidden="true" />
                    ) : item.status.includes('completed') ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" aria-hidden="true" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-red-400" aria-hidden="true" />
                    )}
                    <span role={item.status === 'failed' ? 'alert' : undefined}>
                      {item.error || (item.status.includes('completed') ? 'Evidence đã sẵn sàng cho AI Copilot' : 'Đang xử lý tài liệu...')}
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              type="button"
              onClick={handleUpload}
              disabled={!pendingCount || isUploading}
              className="min-h-11 px-6 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-bold rounded-lg shadow-lg shadow-cyan-900/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 transition-colors"
            >
              {isUploading ? 'Đang tải lên...' : `Tải lên ${pendingCount} tệp`}
            </button>
            {!isUploading && items.some((item) => terminalStatuses.has(item.status)) && (
              <button
                type="button"
                onClick={() => setItems((current) => current.filter((item) => !terminalStatuses.has(item.status)))}
                className="min-h-11 px-4 text-sm text-slate-300 hover:text-white rounded-lg hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                Xóa tệp đã xử lý
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
