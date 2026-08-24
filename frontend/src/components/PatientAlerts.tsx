'use client';

import { useAppStore } from '@/lib/store';
import { AlertTriangle, AlertCircle } from 'lucide-react';

export default function PatientAlerts() {
  const { currentReview, setFocusedCitation, notifyDrugConflict, notifyAbnormalLab } = useAppStore();

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

  if (!currentReview) return null;

  const conflicts = currentReview.conflicts || [];
  const interactions = currentReview.drug_interactions || [];
  const qualityFlags = currentReview.data_quality_flags || [];

  // Respect user notification toggles
  const showHighAlerts = notifyDrugConflict && (conflicts.length > 0 || interactions.some((i: any) => i.severity === 'high' || i.severity === 'moderate'));
  const showMediumAlerts = notifyAbnormalLab && qualityFlags.length > 0;

  if (!showHighAlerts && !showMediumAlerts) return null;

  return (
    <div className="flex flex-col gap-3 mb-2 max-w-full">
      {/* High Severity Alerts */}
      {showHighAlerts && (
        <div className="clinical-card p-4 flex items-start gap-4 border-rose-300 dark:border-rose-900/60 shadow-sm">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center border bg-rose-50 text-rose-600 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-900/60 shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="flex flex-col gap-2.5 w-full">
            <h4 className="text-rose-600 dark:text-rose-400 font-extrabold text-xs tracking-wider uppercase">
              Cảnh báo Mâu thuẫn Lâm sàng &amp; Đơn thuốc
            </h4>
            
            {conflicts.map((conflict: any) => (
              <div key={conflict.conflict_id} className="clinical-subcard p-3 rounded-lg border">
                <div className="mb-2 text-xs font-bold text-slate-900 dark:text-slate-100">
                  <span className="text-rose-600 dark:text-rose-400 font-extrabold mr-1.5">[MÂU THUẪN]:</span> {conflict.description}
                </div>
                <div className="flex flex-wrap gap-2">
                  {conflict.source_a?.map((c: any, i: number) => (
                    <button key={`${c.citation_id || 'sa'}-${i}`} onClick={() => setFocusedCitation(c)} className="text-xs px-2.5 py-1 rounded-md border font-semibold transition-colors cursor-pointer" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--accent-teal)' }}>
                      Nguồn A: {getCitationLabel(c)}
                    </button>
                  ))}
                  {conflict.source_b?.map((c: any, i: number) => (
                    <button key={`${c.citation_id || 'sb'}-${i}`} onClick={() => setFocusedCitation(c)} className="text-xs px-2.5 py-1 rounded-md border font-semibold transition-colors cursor-pointer" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--accent-teal)' }}>
                      Nguồn B: {getCitationLabel(c)}
                    </button>
                  ))}
                </div>
              </div>
            ))}

            {interactions.map((interaction: any, intIdx: number) => (
              <div key={interaction.flag_id || intIdx} className="clinical-subcard p-3 rounded-lg border">
                <div className="mb-2 text-xs font-bold text-slate-900 dark:text-slate-100">
                  <span className="text-rose-600 dark:text-rose-400 font-extrabold mr-1.5">[TƯƠNG TÁC THUỐC {interaction.severity ? `(${interaction.severity.toUpperCase()})` : ''}]:</span> {interaction.description}
                </div>
                <div className="flex flex-wrap gap-2">
                  {interaction.citations?.map((c: any, i: number) => (
                    <button key={`${c.citation_id || 'cit'}-${i}`} onClick={() => setFocusedCitation(c)} className="text-xs px-2.5 py-1 rounded-md border font-semibold transition-colors cursor-pointer" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--accent-teal)' }}>
                      {getCitationLabel(c)}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Medium Severity Alerts */}
      {showMediumAlerts && (
        <div className="clinical-card p-4 flex items-start gap-4 border-amber-300 dark:border-amber-900/60 shadow-sm">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center border bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-900/60 shrink-0">
            <AlertCircle className="w-5 h-5" />
          </div>
          <div className="flex flex-col gap-2 w-full">
            <h4 className="text-amber-600 dark:text-amber-400 font-extrabold text-xs tracking-wider uppercase">
              Lưu ý Dữ liệu &amp; Chất lượng Hồ sơ
            </h4>
            
            {qualityFlags.map((flag: any) => (
              <div key={flag.flag_id} className="clinical-subcard p-2.5 rounded-lg text-xs font-medium text-slate-900 dark:text-slate-100 flex items-start gap-2 border">
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 shrink-0 mt-0.5">{flag.code}</span> 
                <span className="flex-1">{flag.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
