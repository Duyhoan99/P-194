'use client';

import { useState, useEffect } from 'react';
import { patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import {
  Pill,
  AlertTriangle,
  RefreshCw,
  ShieldAlert,
  Activity,
  Calendar
} from 'lucide-react';

interface MedicationEvent {
  event_id: string;
  title: string;
  summary: string;
  occurred_at: string;
  citations?: any[];
  raw?: any;
}

export default function MedicationTimeline({ patientId }: { patientId: string }) {
  const [medEvents, setMedEvents] = useState<MedicationEvent[]>([]);
  const [interactions, setInteractions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { setFocusedCitation, currentReview } = useAppStore();

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError('');

    Promise.all([
      patients.getTimeline(patientId, 1, 100).catch(() => ({ items: [] })),
      patients.getDrugInteractions(patientId).catch(() => ({ interactions: [] }))
    ])
      .then(([timelineRes, interactRes]) => {
        if (!isMounted) return;
        const allItems = timelineRes.items || [];
        const meds = allItems.filter((e: any) => {
          if (e.event_type !== 'medication') return false;
          const cleanTitle = (e.title || '').replace(/^Thuốc:\s*/i, '').trim();
          // Filter out pure dose fragments like "50 mg", "500 mg", "50", "500"
          return !/^\d+(\.\d+)?\s*(mg|g|ml|mcg|ui|iu)?$/i.test(cleanTitle);
        });
        setMedEvents(meds);
        setInteractions(interactRes.interactions || interactRes.items || currentReview?.drug_interactions || []);
      })
      .catch((err: any) => {
        if (!isMounted) return;
        setError(err.detail || 'Không thể tải tiến trình thuốc');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [patientId, currentReview]);

  const handleCitationClick = (citation: any) => {
    setFocusedCitation(citation);
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  // Group medications by title/drug name and deduplicate on same date
  const drugGroups: Record<string, MedicationEvent[]> = {};
  medEvents.forEach(m => {
    const cleanTitle = m.title.replace(/^Thuốc:\s*/i, '').trim();
    if (/^\d+(\.\d+)?\s*(mg|g|ml|mcg|ui|iu)?$/i.test(cleanTitle)) {
      return;
    }
    const nameMatch = cleanTitle.split(' ')[0] || cleanTitle;
    if (!drugGroups[nameMatch]) {
      drugGroups[nameMatch] = [];
    }
    drugGroups[nameMatch].push(m);
  });

  // Deduplicate entries on the same date within each drug group & merge multi-source citations
  Object.keys(drugGroups).forEach(drug => {
    const byDate: Record<string, MedicationEvent> = {};
    drugGroups[drug].forEach(ev => {
      const dKey = (ev.occurred_at || '').substring(0, 10) || 'no_date';
      if (!byDate[dKey]) {
        byDate[dKey] = { ...ev, citations: [...(ev.citations || [])] };
      } else {
        // Merge citations
        const existingCitations = byDate[dKey].citations || [];
        const incomingCitations = ev.citations || [];
        incomingCitations.forEach((inc: any) => {
          if (!existingCitations.some((c: any) => (c.citation_id && c.citation_id === inc.citation_id) || (c.document_id && c.document_id === inc.document_id && c.resource_id === inc.resource_id))) {
            existingCitations.push(inc);
          }
        });
        byDate[dKey].citations = existingCitations;

        // Keep the more descriptive title (e.g. with dosage / brand name)
        if (ev.title.length > byDate[dKey].title.length || (ev.title.includes('mg') && !byDate[dKey].title.includes('mg'))) {
          byDate[dKey].title = ev.title;
        }
        if (ev.summary && (!byDate[dKey].summary || ev.summary.length > byDate[dKey].summary.length)) {
          byDate[dKey].summary = ev.summary;
        }
      }
    });
    drugGroups[drug] = Object.values(byDate).sort((a, b) => 
      new Date(b.occurred_at || '').getTime() - new Date(a.occurred_at || '').getTime()
    );
  });

  return (
    <div className="clinical-card overflow-hidden flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="p-4 px-5 border-b border-[var(--border-card)] bg-[var(--bg-card)] flex items-center justify-between shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/30 text-purple-400">
            <Pill className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 font-extrabold">Tiến trình Sử dụng Thuốc &amp; Phác đồ (Medication Timeline)</h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 font-medium">Theo dõi diễn biến kê đơn, thay đổi liều lượng và cảnh báo tương tác</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-950/80 text-purple-300 border border-purple-800/50">
            {medEvents.length} chỉ định thuốc
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-6 chat-scrollbar pr-3">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-600 dark:text-slate-400 font-medium">
            <RefreshCw className="w-5 h-5 animate-spin mr-2 text-purple-400" />
            <span className="text-sm">Đang phân tích dữ liệu thuốc...</span>
          </div>
        ) : error && medEvents.length === 0 ? (
          <div className="text-center py-12 text-slate-600 dark:text-slate-400 font-medium text-sm">
            <AlertTriangle className="w-8 h-8 text-amber-500/50 mx-auto mb-2" />
            {error}
          </div>
        ) : (
          <>
            {/* 1. Drug Interaction Warning Alert if exists */}
            {interactions.length > 0 && (
              <div className="bg-rose-950/30 border border-rose-900/40 rounded-xl p-4 flex flex-col gap-2.5">
                <div className="flex items-center gap-2 text-rose-300 font-semibold text-xs uppercase tracking-wider">
                  <ShieldAlert className="w-4 h-4 text-rose-400" />
                  <span>Cảnh báo Tương tác &amp; Lưu ý Chức năng Thận</span>
                </div>
                <div className="space-y-2">
                  {interactions.map((inter: any, idx: number) => (
                    <div key={idx} className="clinical-subcard p-2.5 rounded-lg text-xs text-slate-900 dark:text-slate-100 flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <span className="font-medium text-rose-300">
                          {inter.severity ? `[Mức độ: ${inter.severity.toUpperCase()}] ` : ''}{inter.description || inter.message}
                        </span>
                      </div>
                      {inter.citations && inter.citations.length > 0 && (
                        <button
                          onClick={() => handleCitationClick(inter.citations[0])}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-cyan-300 border border-slate-700 shrink-0"
                        >
                          Xem chứng cứ
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 2. Drug Progression Groups */}
            <div className="space-y-5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-2">
                <Activity className="w-3.5 h-3.5" />
                <span>Diễn biến Liều lượng theo Hoạt chất</span>
              </h4>

              {Object.keys(drugGroups).length === 0 ? (
                <div className="text-center py-8 text-slate-500 text-sm">
                  Chưa ghi nhận bản ghi thuốc có cấu trúc nào trong hồ sơ.
                </div>
              ) : (
                Object.entries(drugGroups).map(([drugName, events]) => (
                  <div key={drugName} className="clinical-subcard p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[var(--border-card)] pb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 dark:text-slate-100 font-extrabold text-sm">{drugName}</span>
                        <span className="text-[11px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20 font-medium">
                          {events.length} lần điều chỉnh / kê đơn
                        </span>
                      </div>
                    </div>

                    {/* Timeline steps */}
                    <div className="space-y-2.5 pl-2 border-l-2 border-purple-900/40 ml-1">
                      {events.map((ev, idx) => (
                        <div key={ev.event_id || idx} className="relative pl-4 space-y-1">
                          {/* Dot */}
                          <div className="absolute -left-[9px] top-1.5 w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_6px_rgba(168,85,247,0.8)]" />

                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <span className="font-semibold text-slate-900 dark:text-slate-100 font-bold text-xs">{ev.title}</span>
                            <span className="text-[11px] text-slate-600 dark:text-slate-400 font-medium font-mono flex items-center gap-1">
                              <Calendar className="w-3 h-3 text-slate-500" />
                              {formatDate(ev.occurred_at)}
                            </span>
                          </div>

                          {ev.summary && (
                            <p className="text-xs text-slate-600 dark:text-slate-400 font-medium leading-relaxed">{ev.summary}</p>
                          )}

                          {ev.citations && ev.citations.length > 0 && (
                            <div className="flex gap-1.5 pt-1 flex-wrap">
                              {ev.citations.map((c: any, cIdx: number) => {
                                const rawType = (c.source_type || '').toLowerCase();
                                const docName = (c.document_name || c.document_id || c.citation_id || '').toLowerCase();

                                let label = 'PDF';
                                let colorCls = 'bg-indigo-950/90 text-indigo-300 border-indigo-600/80 hover:border-indigo-300 shadow-[0_0_8px_rgba(99,102,241,0.2)]';
                                let icon = '📄';

                                if (rawType === 'ocr' || docName.includes('scan') || docName.includes('photo') || docName.endsWith('.jpg') || docName.endsWith('.png') || docName.endsWith('.jpeg')) {
                                  label = 'OCR';
                                  colorCls = 'bg-amber-950/90 text-amber-300 border-amber-600/80 hover:border-amber-300 shadow-[0_0_8px_rgba(245,158,11,0.2)]';
                                  icon = '📷';
                                } else if (rawType === 'pdf' || docName.includes('pdf') || docName.endsWith('.pdf') || docName.includes('doc_') || docName.includes('prescription') || docName.includes('phieu_kham') || docName.includes('followup') || docName.includes('lab_report')) {
                                  label = 'PDF';
                                  colorCls = 'bg-indigo-950/90 text-indigo-300 border-indigo-600/80 hover:border-indigo-300 shadow-[0_0_8px_rgba(99,102,241,0.2)]';
                                  icon = '📄';
                                } else if (rawType === 'fhir' || docName.includes('fhir') || docName.endsWith('.json') || docName.includes('bundle') || c.resource_type || c.resource_id) {
                                  label = 'FHIR';
                                  colorCls = 'bg-cyan-950/90 text-cyan-300 border-cyan-600/80 hover:border-cyan-300 shadow-[0_0_8px_rgba(6,182,212,0.2)]';
                                  icon = '⚡';
                                } else if (rawType === 'canonical_record' || rawType === 'ehr') {
                                  label = 'EHR';
                                  colorCls = 'bg-emerald-950/90 text-emerald-300 border-emerald-600/80 hover:border-emerald-300 shadow-[0_0_8px_rgba(16,185,129,0.2)]';
                                  icon = '🏥';
                                }

                                return (
                                  <button
                                    key={cIdx}
                                    onClick={() => handleCitationClick(c)}
                                    className={`inline-flex items-center gap-1 min-w-[34px] h-[20px] px-1.5 text-[10px] font-extrabold font-mono border rounded-md cursor-pointer transition-all ${colorCls}`}
                                    title={`Nhấp để mở nguồn chứng cứ gốc [${label}]: ${c.document_name || c.resource_type || 'Đơn thuốc'}`}
                                  >
                                    <span>{icon}</span>
                                    <span>{label}</span>
                                    {(ev.citations?.length ?? 0) > 1 && <span className="opacity-75 text-[9px]">#{cIdx + 1}</span>}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
