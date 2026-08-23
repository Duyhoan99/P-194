'use client';

import { useAppStore } from '@/lib/store';
import {
  AlertTriangle,
  AlertCircle,
  FileText,
  CheckCircle2,
  Eye,
  ShieldCheck,
  SplitSquareVertical
} from 'lucide-react';

export default function DataConflictsPanel() {
  const { currentReview, setFocusedCitation } = useAppStore();

  const getCitationLabel = (cit: any) => {
    if (cit.source_type === 'pdf') {
      return `📄 ${cit.document_name || 'Tài liệu'}${cit.page_number ? ` (Tr. ${cit.page_number})` : ''}`;
    }
    const dateMatch = cit.snippet?.match(/\d{4}-\d{2}-\d{2}/) || cit.source_time?.match(/\d{4}-\d{2}-\d{2}/);
    const dateStr = dateMatch ? dateMatch[0].split('-').reverse().join('/') : '';
    if (cit.resource_type) {
      let typeName = cit.resource_type;
      if (typeName === 'Observation') typeName = 'Xét nghiệm';
      if (typeName === 'Encounter') typeName = 'Lượt khám';
      if (typeName === 'MedicationRequest') typeName = 'Đơn thuốc';
      if (typeName === 'Condition') typeName = 'Chẩn đoán';
      return `📎 Nguồn: ${typeName}${dateStr ? ` · ${dateStr}` : ''}`;
    }
    return `📎 Nguồn hồ sơ${dateStr ? ` · ${dateStr}` : ''}`;
  };

  const conflicts = currentReview?.conflicts || [];
  const qualityFlags = currentReview?.data_quality_flags || [];

  return (
    <div className="clinical-card overflow-hidden flex flex-col h-full min-h-0 shadow-sm">
      {/* Header */}
      <div className="p-4 px-5 border-b flex items-center justify-between shrink-0 flex-wrap gap-2" style={{ borderColor: 'var(--border-card)', backgroundColor: 'var(--bg-card)' }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center border shadow-sm" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
            <SplitSquareVertical className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-slate-900 dark:text-slate-100">
              Đối soát &amp; Mâu thuẫn Dữ liệu Đa Nguồn
            </h3>
            <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Phát hiện sai lệch giữa Hồ sơ số (FHIR), Đơn thuốc scan (OCR) và Bệnh sử
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold px-3 py-1 rounded-full border ${
            conflicts.length > 0
              ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
              : 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
          }`}>
            {conflicts.length > 0 ? `⚠️ ${conflicts.length} mâu thuẫn cần xác minh` : '✓ Không có mâu thuẫn dữ liệu'}
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-6 chat-scrollbar pr-3">
        
        {/* Section 1: Side-by-Side Data Conflicts */}
        <div className="space-y-4">
          <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
            <span>Mâu thuẫn Dữ liệu Đối chiếu (Side-by-Side Discrepancies)</span>
          </h4>

          {conflicts.length === 0 ? (
            <div className="clinical-subcard p-8 text-center flex flex-col items-center justify-center gap-2 rounded-2xl border">
              <div className="w-10 h-10 rounded-full flex items-center justify-center border text-emerald-600 bg-emerald-50 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <p className="text-sm font-extrabold text-slate-900 dark:text-slate-100">Không ghi nhận mâu thuẫn đối kháng</p>
              <p className="text-xs font-medium max-w-md" style={{ color: 'var(--text-muted)' }}>
                Tất cả các nguồn dữ liệu số hóa (EHR, Lab LIS, Đơn thuốc) đều đồng nhất về liều dùng, chẩn đoán và chỉ số xét nghiệm.
              </p>
            </div>
          ) : (
            conflicts.map((conflict: any, idx: number) => (
              <div key={conflict.conflict_id || idx} className="clinical-card p-5 space-y-4 border border-rose-200 dark:border-rose-900/40 shadow-sm rounded-2xl">
                
                {/* Topic Header */}
                <div className="flex items-center justify-between border-b pb-3 flex-wrap gap-2" style={{ borderColor: 'var(--border-card)' }}>
                  <div className="flex items-center gap-2.5">
                    <span className="text-[11px] font-extrabold text-white bg-rose-600 px-2.5 py-0.5 rounded-md shadow-sm">
                      MÂU THUẪN #{idx + 1}
                    </span>
                    <span className="text-sm font-extrabold text-slate-900 dark:text-slate-100">
                      {conflict.topic || conflict.description}
                    </span>
                  </div>
                  <span className="text-xs font-bold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 px-2.5 py-1 rounded-lg border border-rose-200 dark:border-rose-900/50">
                    Cần bác sĩ xác minh
                  </span>
                </div>

                {/* Side by side boxes */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                  
                  {/* Source A */}
                  <div className="clinical-subcard p-4 rounded-xl border flex flex-col justify-between space-y-3 shadow-none" style={{ borderColor: 'var(--border-card)' }}>
                    <div className="space-y-1.5">
                      <div className="text-xs font-extrabold text-teal-700 dark:text-teal-400 uppercase tracking-wider flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5" />
                        <span>Nguồn A: Hồ sơ Hệ thống số (FHIR)</span>
                      </div>
                      <p className="text-xs sm:text-sm font-medium text-slate-900 dark:text-slate-100 leading-relaxed">
                        {conflict.source_a_text || conflict.description || 'Ghi nhận liều dùng từ hệ thống quản lý bệnh án điện tử'}
                      </p>
                    </div>

                    <div className="pt-2 border-t flex flex-wrap gap-1.5" style={{ borderColor: 'var(--border-card)' }}>
                      {conflict.source_a?.map((c: any, i: number) => (
                        <button
                          key={i}
                          onClick={() => setFocusedCitation(c)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-xs font-semibold transition-all hover:scale-105 cursor-pointer"
                          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}
                        >
                          <Eye className="w-3.5 h-3.5" /> <span>{getCitationLabel(c)}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Source B */}
                  <div className="clinical-subcard p-4 rounded-xl border flex flex-col justify-between space-y-3 shadow-none" style={{ borderColor: 'var(--border-card)' }}>
                    <div className="space-y-1.5">
                      <div className="text-xs font-extrabold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5" />
                        <span>Nguồn B: Đơn thuốc Scan / Giấy tờ OCR</span>
                      </div>
                      <p className="text-xs sm:text-sm font-medium text-slate-900 dark:text-slate-100 leading-relaxed">
                        {conflict.source_b_text || conflict.resolution_note || 'Ghi nhận liều dùng khác biệt từ tài liệu giấy quét OCR/PDF'}
                      </p>
                    </div>

                    <div className="pt-2 border-t flex flex-wrap gap-1.5" style={{ borderColor: 'var(--border-card)' }}>
                      {conflict.source_b?.map((c: any, i: number) => (
                        <button
                          key={i}
                          onClick={() => setFocusedCitation(c)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-xs font-semibold transition-all hover:scale-105 cursor-pointer"
                          style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--text-primary)' }}
                        >
                          <Eye className="w-3.5 h-3.5" /> <span>{getCitationLabel(c)}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                </div>

                {/* Safety Rule Note */}
                <div className="clinical-subcard p-3 rounded-xl border text-xs font-medium text-slate-800 dark:text-slate-200 flex items-center gap-2" style={{ borderColor: 'var(--border-card)' }}>
                  <ShieldCheck className="w-4 h-4 text-teal-600 dark:text-teal-400 shrink-0" />
                  <span>
                    <strong className="text-slate-900 dark:text-slate-100">Nguyên tắc An toàn:</strong> AI bảo lưu cả 2 nguồn và không tự suy đoán. Bác sĩ vui lòng đối chiếu người bệnh để xác nhận phác đồ chuẩn.
                  </span>
                </div>

              </div>
            ))
          )}
        </div>

        {/* Section 2: Data Quality & Missing Information Gaps */}
        <div className="space-y-3 pt-4 border-t" style={{ borderColor: 'var(--border-card)' }}>
          <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" style={{ color: 'var(--accent-teal)' }} />
            <span>Khoảng trống &amp; Cảnh báo Chất lượng Dữ liệu (Data Gaps)</span>
          </h4>

          {qualityFlags.length === 0 ? (
            <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Không ghi nhận khoảng trống dữ liệu nghiêm trọng.</p>
          ) : (
            <div className="space-y-2">
              {qualityFlags.map((flag: any, idx: number) => (
                <div key={flag.flag_id || idx} className="clinical-subcard p-3.5 rounded-xl border flex items-start gap-3 text-xs" style={{ borderColor: 'var(--border-card)' }}>
                  <span className="font-mono text-[10px] font-extrabold px-2 py-0.5 rounded border shrink-0 mt-0.5" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
                    {flag.code || 'DATA_GAP'}
                  </span>
                  <span className="text-slate-900 dark:text-slate-100 font-semibold leading-relaxed flex-1">
                    {flag.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
