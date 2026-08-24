'use client';

import { useEffect, useRef, useState } from 'react';
import { ingestions, patients } from '@/lib/api';
import { AlertCircle, CheckCircle2, FileText, Loader2, UploadCloud, UserCheck, X, Sparkles, Plus } from 'lucide-react';
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
  const { selectedPatient, triggerRefresh, refreshTrigger } = useAppStore();
  const contextPatientId = selectedPatient?.patient_id || '';
  const [patientList, setPatientList] = useState<any[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string>(contextPatientId || 'auto');
  const [newPatientName, setNewPatientName] = useState('');
  const [items, setItems] = useState<UploadItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadPatients = async () => {
    try {
      const res = await patients.list({ page_size: 50 });
      if (res?.items) {
        setPatientList(res.items);
      }
    } catch {}
  };

  useEffect(() => {
    loadPatients();
  }, [refreshTrigger]);

  const updateItem = (id: string, patch: Partial<UploadItem>) => {
    setItems((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  };

  const addFiles = (files: File[]) => {
    setItems((current) => {
      const newFileIds = new Set(files.map(fileId));
      const remaining = current.filter((item) => !newFileIds.has(item.id));
      const additions = files.map((file) => ({
        id: fileId(file),
        file,
        status: 'queued' as const,
        progress: 0,
      }));
      return [...remaining, ...additions];
    });
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files || []));
    event.target.value = '';
  };

  const handleRetryItem = (id: string) => {
    updateItem(id, { status: 'queued', progress: 0, error: undefined });
  };

  const handleRemoveItem = (id: string) => {
    setItems((current) => current.filter((candidate) => candidate.id !== id));
  };

  const handleClearCompleted = () => {
    setItems((current) => current.filter((item) => !item.status.includes('completed')));
  };

  const pollStatus = async (itemId: string, batchId: string) => {
    for (let attempt = 0; attempt < 60; attempt += 1) {
      await sleep(1500);
      try {
        const batch = await ingestions.getStatus(batchId);
        const status = batch.status as UploadStatus;
        if (terminalStatuses.has(status)) {
          return { status, error: batch.error_message || undefined };
        }
      } catch (error) {
        return {
          status: 'failed' as const,
          error: error instanceof Error ? error.message : 'Không thể kiểm tra tiến trình xử lý.',
        };
      }
    }
    return {
      status: 'failed' as const,
      error: 'Quá thời gian xử lý tài liệu.',
    };
  };

  const handleUploadAll = async () => {
    const queue = items.filter((item) => item.status === 'queued' || item.status === 'failed');
    if (queue.length === 0 || isUploading) return;

    setIsUploading(true);
    let boundPid = contextPatientId || (selectedTarget !== 'auto' && selectedTarget !== 'new' ? selectedTarget : undefined);
    let targetName = selectedTarget === 'new' && newPatientName.trim() ? newPatientName.trim() : undefined;

    try {
      for (const item of queue) {
        updateItem(item.id, { status: 'uploading', progress: 15, error: undefined });

        try {
          const result = await ingestions.upload(item.file, boundPid, targetName);
          if (result.patient_id) {
            boundPid = result.patient_id;
          }
          if (selectedTarget === 'new') {
            targetName = undefined;
          }

          const initialStatus = result.status as UploadStatus;
          updateItem(item.id, {
            batchId: result.batch_id,
            status: terminalStatuses.has(initialStatus) ? initialStatus : 'processing',
            progress: terminalStatuses.has(initialStatus) ? 100 : 25,
          });
          if (!terminalStatuses.has(initialStatus)) {
            const finalResult = await pollStatus(item.id, result.batch_id);
            updateItem(item.id, { status: finalResult.status, progress: 100, error: finalResult.error });
          }
        } catch (error) {
          updateItem(item.id, {
            status: 'failed',
            progress: 100,
            error: error instanceof Error ? error.message : 'Xử lý tài liệu thất bại.',
          });
        }
      }
    } finally {
      setIsUploading(false);
      await loadPatients();
      triggerRefresh();
      onUploadComplete?.();
    }
  };

  const pendingCount = items.filter((item) => item.status === 'queued' || item.status === 'failed').length;
  const failedCount = items.filter((item) => item.status === 'failed').length;
  const completedCount = items.filter((item) => item.status.includes('completed')).length;

  return (
    <div className="clinical-card p-6 space-y-5 shadow-sm">
      {/* Title */}
      <h3 className="text-sm font-extrabold tracking-tight flex items-center gap-2" style={{ color: 'var(--accent-teal)' }}>
        <UploadCloud className="w-4 h-4" />
        <span>Tải lên Hồ sơ &amp; Tài liệu Lâm sàng</span>
      </h3>

      {/* Target Patient Selector */}
      {!contextPatientId && (
        <div className="space-y-3">
          <div className="space-y-1.5">
            <label htmlFor="target-patient" className="block text-xs font-bold text-slate-900 dark:text-slate-100">
              Hồ sơ bệnh nhân đích (Target Patient)
            </label>
            <select
              id="target-patient"
              value={selectedTarget}
              disabled={isUploading}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className="clinical-input w-full px-4 py-2.5 text-xs font-semibold"
            >
              <option value="auto">✨ Tự động nhận diện từ tài liệu (AI Auto-detect)</option>
              <option value="new">➕ Tạo mới hồ sơ bệnh nhân...</option>
              <option disabled>────────── Danh sách hồ sơ có sẵn ──────────</option>
              {patientList.map((p) => (
                <option key={p.patient_id} value={p.patient_id}>
                  👤 {p.pseudonym} ({p.patient_id})
                </option>
              ))}
            </select>
          </div>

          {selectedTarget === 'new' && (
            <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="space-y-1.5">
              <label htmlFor="new-patient-name" className="block text-xs font-bold text-slate-900 dark:text-slate-100">
                Tên bệnh nhân mới
              </label>
              <input
                id="new-patient-name"
                type="text"
                value={newPatientName}
                disabled={isUploading}
                onChange={(event) => setNewPatientName(event.target.value)}
                placeholder="VD: Nguyễn Văn A..."
                className="clinical-input w-full px-4 py-2.5 text-xs font-medium"
              />
            </motion.div>
          )}
        </div>
      )}

      {contextPatientId && (
        <p className="text-xs font-medium flex items-center gap-1.5" style={{ color: 'var(--accent-teal)' }}>
          <UserCheck className="w-4 h-4" />
          Tất cả tệp sẽ được thêm vào bệnh nhân <span className="font-extrabold">{contextPatientId}</span>.
        </p>
      )}

      {/* Hidden File Input */}
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

      {/* Drop Zone Box */}
      <div
        className={`clinical-subcard border-2 border-dashed rounded-2xl p-8 transition-all text-center cursor-pointer ${
          isDragging ? 'border-teal-500 scale-[1.01]' : 'hover:border-teal-500'
        }`}
        style={{ borderColor: isDragging ? 'var(--accent-teal)' : 'var(--accent-teal-border)' }}
        onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => { event.preventDefault(); setIsDragging(false); }}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          if (!isUploading) addFiles(Array.from(event.dataTransfer.files));
        }}
        onClick={() => !isUploading && fileInputRef.current?.click()}
      >
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center border shadow-sm mx-auto mb-3.5 transition-transform hover:scale-105" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
          <UploadCloud className="w-8 h-8" />
        </div>
        <p className="text-sm font-extrabold text-slate-900 dark:text-slate-100">
          Chọn nhiều tệp hoặc kéo thả vào đây
        </p>
        <p className="text-xs font-semibold mt-1" style={{ color: 'var(--text-secondary)' }}>
          Hỗ trợ: PDF, PNG/JPG hoặc FHIR R4 JSON
        </p>
      </div>

      {/* Upload Item Queue */}
      {items.length > 0 && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
              Danh sách tệp ({items.length})
            </span>
            {completedCount > 0 && !isUploading && (
              <button
                type="button"
                onClick={handleClearCompleted}
                className="text-[11px] font-semibold text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
              >
                Dọn tệp đã xong
              </button>
            )}
          </div>

          {items.map((item) => (
            <div key={item.id} className="clinical-subcard p-3.5 rounded-xl border flex flex-col gap-2 shadow-sm" style={{ borderColor: 'var(--border-card)' }}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center border shrink-0" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--accent-teal)' }}>
                    <FileText className="w-4 h-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-slate-900 dark:text-slate-100">{item.file.name}</p>
                    <p className="text-[11px] font-medium" style={{ color: 'var(--text-muted)' }}>{(item.file.size / 1024).toFixed(1)} KB</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${
                    item.status === 'failed' ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800' :
                    item.status.includes('completed') ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800' :
                    item.status === 'uploading' || item.status === 'processing' ? 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800' :
                    'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
                  }`}>
                    {item.status === 'queued' ? 'Chờ tải lên' :
                     item.status === 'uploading' ? 'Đang tải...' :
                     item.status === 'processing' ? 'Đang phân tích...' :
                     item.status.includes('completed') ? 'Hoàn tất' : 'Lỗi'}
                  </span>

                  {item.status === 'failed' && !isUploading && (
                    <button
                      type="button"
                      onClick={() => handleRetryItem(item.id)}
                      className="px-2 py-1 text-[11px] font-bold rounded-lg bg-teal-50 dark:bg-teal-950/50 text-teal-700 dark:text-teal-300 border border-teal-300 dark:border-teal-700 hover:bg-teal-100 transition-colors flex items-center gap-1 cursor-pointer"
                      title="Thử lại tệp này"
                    >
                      <Sparkles className="w-3 h-3" />
                      <span>Thử lại</span>
                    </button>
                  )}

                  {!isUploading && (
                    <button
                      type="button"
                      onClick={() => handleRemoveItem(item.id)}
                      className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 transition-colors cursor-pointer"
                      title="Xóa tệp khỏi danh sách"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {item.error && (
                <div className="text-[11px] font-medium text-rose-600 dark:text-rose-400 bg-rose-50/50 dark:bg-rose-950/30 px-2.5 py-1 rounded-lg border border-rose-200 dark:border-rose-900/50 flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{item.error}</span>
                </div>
              )}
            </div>
          ))}

          {/* Action Bar */}
          {pendingCount > 0 && (
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                disabled={isUploading}
                onClick={handleUploadAll}
                className="px-5 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-sm flex items-center gap-2 cursor-pointer transition-all"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Đang xử lý hồ sơ...</span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4" />
                    <span>
                      {failedCount > 0 && pendingCount === failedCount
                        ? `Thử lại tất cả (${failedCount} tệp lỗi)`
                        : `Tiến hành tải lên (${pendingCount} tệp)`}
                    </span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
