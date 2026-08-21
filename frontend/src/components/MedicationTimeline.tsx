'use client';

import { useState, useEffect } from 'react';
import { patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import {
  Pill,
  Clock,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  ArrowRight,
  ShieldAlert,
  FileText,
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
        const meds = allItems.filter((e: any) => e.event_type === 'medication');
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

  // Group medications by title/drug name if possible
  const drugGroups: Record<string, MedicationEvent[]> = {};
  medEvents.forEach(m => {
    // Extract base drug name, e.g. "Metformin" from "Metformin 500 MG"
    const nameMatch = m.title.replace(/^Thuốc:\s*/i, '').split(' ')[0] || m.title;
    if (!drugGroups[nameMatch]) {
      drugGroups[nameMatch] = [];
    }
    drugGroups[nameMatch].push(m);
  });

  return (
    <div className="bg-slate-950/70 backdrop-blur-xl border border-white/10 rounded-2xl shadow-xl overflow-hidden flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="p-4 px-5 border-b border-white/10 bg-slate-900/90 flex items-center justify-between shrink-0 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/30 text-purple-400">
            <Pill className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">Tiến trình Sử dụng Thuốc &amp; Phác đồ (Medication Timeline)</h3>
            <p className="text-xs text-slate-400">Theo dõi diễn biến kê đơn, thay đổi liều lượng và cảnh báo tương tác</p>
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
          <div className="flex items-center justify-center py-16 text-slate-400">
            <RefreshCw className="w-5 h-5 animate-spin mr-2 text-purple-400" />
            <span className="text-sm">Đang phân tích dữ liệu thuốc...</span>
          </div>
        ) : error && medEvents.length === 0 ? (
          <div className="text-center py-12 text-slate-400 text-sm">
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
                    <div key={idx} className="bg-slate-900/80 p-2.5 rounded-lg border border-rose-900/30 text-xs text-slate-300 flex items-start justify-between gap-3">
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
                  <div key={drugName} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-100 text-sm">{drugName}</span>
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
                            <span className="font-semibold text-slate-200 text-xs">{ev.title}</span>
                            <span className="text-[11px] text-slate-400 font-mono flex items-center gap-1">
                              <Calendar className="w-3 h-3 text-slate-500" />
                              {formatDate(ev.occurred_at)}
                            </span>
                          </div>

                          {ev.summary && (
                            <p className="text-xs text-slate-400 leading-relaxed">{ev.summary}</p>
                          )}

                          {ev.citations && ev.citations.length > 0 && (
                            <div className="flex gap-1.5 pt-1 flex-wrap">
                              {ev.citations.map((c: any, cIdx: number) => (
                                <button
                                  key={cIdx}
                                  onClick={() => handleCitationClick(c)}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-900 hover:bg-cyan-950/60 text-[10px] text-cyan-300 hover:text-cyan-200 rounded border border-slate-800 hover:border-cyan-500/40 transition-colors"
                                >
                                  📄 Nguồn: {c.document_name || c.resource_type || 'Đơn thuốc'}
                                </button>
                              ))}
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
