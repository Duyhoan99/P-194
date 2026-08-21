'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import {
  AlertTriangle,
  AlertCircle,
  FileText,
  CheckCircle2,
  HelpCircle,
  Eye,
  ShieldCheck,
  SplitSquareVertical,
  ArrowRight
} from 'lucide-react';

export default function DataConflictsPanel({ patientId }: { patientId: string }) {
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
    <div className="bg-slate-950/70 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl overflow-hidden flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="p-4 px-5 border-b border-white/10 bg-slate-900/90 flex items-center justify-between shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/30 text-amber-400">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">Đối soát &amp; Mâu thuẫn Dữ liệu Đa Nguồn (Conflict Inspector)</h3>
            <p className="text-xs text-slate-400">Tự động phát hiện sai lệch giữa Hồ sơ số (FHIR), Đơn thuốc scan (OCR) và Bệnh sử</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono px-2.5 py-1 rounded-full font-bold border ${
            conflicts.length > 0
              ? 'bg-rose-950/80 text-rose-300 border-rose-800/50'
              : 'bg-emerald-950/80 text-emerald-300 border-emerald-800/50'
          }`}>
            {conflicts.length > 0 ? `⚠️ ${conflicts.length} mâu thuẫn cần xác minh` : '✓ Không có xung đột dữ liệu'}
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-6 chat-scrollbar pr-3">
        
        {/* Section 1: Side-by-Side Data Conflicts */}
        <div className="space-y-4">
          <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-2">
            <SplitSquareVertical className="w-4 h-4 text-amber-400" />
            <span>Mâu thuẫn Dữ liệu Đối chiếu (Side-by-Side Discrepancies)</span>
          </h4>

          {conflicts.length === 0 ? (
            <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-8 text-center flex flex-col items-center justify-center gap-2">
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 text-emerald-400">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <p className="text-sm font-semibold text-slate-200">Không ghi nhận mâu thuẫn đối kháng</p>
              <p className="text-xs text-slate-400 max-w-md">
                Tất cả các nguồn dữ liệu số hóa (EHR, Lab LIS, Đơn thuốc) đều đồng nhất về liều dùng, chẩn đoán và chỉ số xét nghiệm.
              </p>
            </div>
          ) : (
            conflicts.map((conflict: any, idx: number) => (
              <div key={conflict.conflict_id || idx} className="bg-slate-900/80 border border-amber-500/30 rounded-xl p-4 space-y-3 shadow-lg">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2.5 flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-rose-300 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                      MÂU THUẪN #{idx + 1}
                    </span>
                    <span className="text-xs font-semibold text-slate-200">{conflict.topic || conflict.description}</span>
                  </div>
                  <span className="text-[11px] font-mono text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-500/20">
                    Trạng thái: CẦN BÁC SĨ XÁC MINH
                  </span>
                </div>

                {/* Side by side boxes */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                  {/* Source A */}
                  <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 space-y-2 flex flex-col justify-between">
                    <div>
                      <div className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Nguồn Dữ liệu A (Hồ sơ Hệ thống số / FHIR)</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {conflict.source_a_text || conflict.description || 'Ghi nhận liều dùng từ hệ thống quản lý bệnh án điện tử'}
                      </p>
                    </div>

                    <div className="pt-2 border-t border-slate-900 flex flex-wrap gap-1.5">
                      {conflict.source_a?.map((c: any, i: number) => (
                        <button
                          key={i}
                          onClick={() => setFocusedCitation(c)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-slate-900 hover:bg-cyan-950 text-[11px] text-cyan-300 rounded border border-cyan-800/40 transition-colors"
                        >
                          <Eye className="w-3 h-3" /> {getCitationLabel(c)}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Source B */}
                  <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 space-y-2 flex flex-col justify-between">
                    <div>
                      <div className="text-[11px] font-bold text-amber-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-amber-400" />
                        <span>Nguồn Dữ liệu B (Đơn thuốc Scan / Bệnh sử)</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {conflict.source_b_text || conflict.resolution_note || 'Ghi nhận liều dùng khác biệt từ tài liệu giấy quét OCR/PDF'}
                      </p>
                    </div>

                    <div className="pt-2 border-t border-slate-900 flex flex-wrap gap-1.5">
                      {conflict.source_b?.map((c: any, i: number) => (
                        <button
                          key={i}
                          onClick={() => setFocusedCitation(c)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-slate-900 hover:bg-amber-950 text-[11px] text-amber-300 rounded border border-amber-800/40 transition-colors"
                        >
                          <Eye className="w-3 h-3" /> {getCitationLabel(c)}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="bg-slate-950/40 p-2.5 rounded-lg border border-white/5 text-[11px] text-slate-400 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-teal-400 shrink-0" />
                  <span>
                    <strong>Nguyên tắc An toàn:</strong> AI Co-pilot bảo lưu cả 2 nguồn và không tự ý quyết định. Bác sĩ vui lòng đối chiếu người bệnh để xác nhận phác đồ chuẩn.
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Section 2: Data Quality & Missing Information Gaps */}
        <div className="space-y-3 pt-4 border-t border-slate-800">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-cyan-400" />
            <span>Khoảng trống &amp; Cảnh báo Chất lượng Dữ liệu (Data Gaps)</span>
          </h4>

          {qualityFlags.length === 0 ? (
            <p className="text-xs text-slate-500">Không ghi nhận khoảng trống dữ liệu nghiêm trọng.</p>
          ) : (
            <div className="space-y-2">
              {qualityFlags.map((flag: any, idx: number) => (
                <div key={flag.flag_id || idx} className="bg-slate-900/60 border border-slate-800 p-3 rounded-xl flex items-start justify-between gap-3 text-xs">
                  <div className="flex items-start gap-2.5">
                    <span className="font-mono text-[10px] font-bold text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/40 shrink-0 mt-0.5">
                      {flag.code || 'DATA_GAP'}
                    </span>
                    <span className="text-slate-300 leading-relaxed">{flag.message}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
