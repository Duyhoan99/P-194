'use client';

import { useAppStore } from '@/lib/store';
import { AlertTriangle, AlertCircle } from 'lucide-react';

export default function PatientAlerts() {
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

  if (!currentReview) return null;

  const conflicts = currentReview.conflicts || [];
  const interactions = currentReview.drug_interactions || [];
  const qualityFlags = currentReview.data_quality_flags || [];

  const hasHighAlerts = conflicts.length > 0 || interactions.some((i: any) => i.severity === 'high' || i.severity === 'moderate');
  const hasMediumAlerts = qualityFlags.length > 0;

  if (!hasHighAlerts && !hasMediumAlerts) return null;

  return (
    <div className="flex flex-col gap-3 mt-5 max-w-4xl">
      {/* High Severity Alerts */}
      {hasHighAlerts && (
        <div className="bg-rose-950/40 border border-rose-900/50 rounded-xl p-4 flex items-start gap-4 shadow-lg shadow-rose-900/10 backdrop-blur-sm">
          <div className="bg-rose-900/40 p-2 rounded-lg shrink-0">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
          </div>
          <div className="flex flex-col gap-3 w-full">
            <h4 className="text-rose-400 font-semibold text-sm tracking-wide uppercase">Critical Clinical Alerts</h4>
            
            {conflicts.map((conflict: any) => (
              <div key={conflict.conflict_id} className="text-sm text-slate-300 bg-black/20 p-3 rounded-lg border border-rose-900/30">
                <div className="mb-2"><span className="font-medium text-rose-300">Data Conflict:</span> {conflict.description}</div>
                <div className="flex flex-wrap gap-2">
                  {conflict.source_a?.map((c: any, i: number) => (
                    <button key={`${c.citation_id || 'sa'}-${i}`} onClick={() => setFocusedCitation(c)} className="text-xs px-2.5 py-1 bg-rose-900/30 text-rose-300 rounded-md hover:bg-rose-900/50 transition-colors border border-rose-800/30">
                      Nguồn A: {getCitationLabel(c)}
                    </button>
                  ))}
                  {conflict.source_b?.map((c: any, i: number) => (
                    <button key={`${c.citation_id || 'sb'}-${i}`} onClick={() => setFocusedCitation(c)} className="text-xs px-2.5 py-1 bg-rose-900/30 text-rose-300 rounded-md hover:bg-rose-900/50 transition-colors border border-rose-800/30">
                      Nguồn B: {getCitationLabel(c)}
                    </button>
                  ))}
                </div>
              </div>
            ))}

            {interactions.map((interaction: any, intIdx: number) => (
              <div key={interaction.flag_id || intIdx} className="text-sm text-slate-300 bg-black/20 p-3 rounded-lg border border-rose-900/30">
                <div className="mb-2"><span className="font-medium text-rose-300">Drug Interaction ({interaction.severity}):</span> {interaction.description}</div>
                <div className="flex flex-wrap gap-2">
                  {interaction.citations?.map((c: any, i: number) => (
                    <button key={`${c.citation_id || 'cit'}-${i}`} onClick={() => setFocusedCitation(c)} className="text-xs px-2.5 py-1 bg-rose-900/30 text-rose-300 rounded-md hover:bg-rose-900/50 transition-colors border border-rose-800/30">
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
      {hasMediumAlerts && (
        <div className="bg-amber-950/30 border border-amber-900/40 rounded-xl p-4 flex items-start gap-4 shadow-lg shadow-amber-900/5 backdrop-blur-sm">
          <div className="bg-amber-900/30 p-2 rounded-lg shrink-0">
            <AlertCircle className="w-5 h-5 text-amber-400" />
          </div>
          <div className="flex flex-col gap-2 w-full">
            <h4 className="text-amber-400 font-semibold text-sm tracking-wide uppercase">Data & Quality Warnings</h4>
            
            {qualityFlags.map((flag: any) => (
              <div key={flag.flag_id} className="text-sm text-slate-300 flex items-start gap-2 bg-black/10 p-2.5 rounded-lg">
                <span className="font-mono text-xs text-amber-500/70 mt-0.5 bg-amber-900/20 px-1.5 rounded">{flag.code}</span> 
                <span className="flex-1">{flag.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
