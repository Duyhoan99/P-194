'use client';

import { useState, useEffect } from 'react';
import { patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { Calendar, Stethoscope, Pill, FlaskConical, FileText, AlertTriangle, Heart, ChevronDown, RefreshCw } from 'lucide-react';

const EVENT_CONFIG: Record<string, { icon: typeof Calendar; color: string; bg: string; border: string }> = {
  encounter:   { icon: Stethoscope,   color: 'text-blue-400',    bg: 'bg-blue-500/10',    border: 'border-blue-500/20' },
  observation: { icon: FlaskConical,  color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  medication:  { icon: Pill,          color: 'text-purple-400',  bg: 'bg-purple-500/10',  border: 'border-purple-500/20' },
  condition:   { icon: Heart,         color: 'text-rose-400',    bg: 'bg-rose-500/10',    border: 'border-rose-500/20' },
  allergy:     { icon: AlertTriangle, color: 'text-amber-400',   bg: 'bg-amber-500/10',   border: 'border-amber-500/20' },
  note:        { icon: FileText,      color: 'text-slate-400',   bg: 'bg-slate-500/10',   border: 'border-slate-500/20' },
};

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function Timeline({ patientId }: { patientId: string }) {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);
  const { setFocusedCitation } = useAppStore();

  useEffect(() => {
    setLoading(true);
    setError('');
    patients.getTimeline(patientId, 1, 50)
      .then((res) => {
        setEvents(res.items || []);
      })
      .catch((err: any) => {
        setError(err.detail || 'Failed to load timeline');
      })
      .finally(() => setLoading(false));
  }, [patientId]);

  const handleCitationClick = (citation: any) => {
    setFocusedCitation(citation);
  };

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

  if (loading) {
    return (
      <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <Calendar className="w-5 h-5 text-cyan-400" />
          <h3 className="text-lg font-bold text-slate-100">Clinical Timeline</h3>
        </div>
        <div className="flex items-center justify-center py-8 text-slate-500">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" />
          <span className="text-sm">Loading timeline...</span>
        </div>
      </div>
    );
  }

  if (error && events.length === 0) {
    return (
      <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <Calendar className="w-5 h-5 text-cyan-400" />
          <h3 className="text-lg font-bold text-slate-100">Clinical Timeline</h3>
        </div>
        <div className="text-center py-6 text-sm text-slate-500">{error}</div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <Calendar className="w-5 h-5 text-cyan-400" />
          <h3 className="text-lg font-bold text-slate-100">Clinical Timeline</h3>
        </div>
        <div className="text-center py-6 text-sm text-slate-500">No timeline events available yet.</div>
      </div>
    );
  }

  // Group events by date
  const grouped: Record<string, any[]> = {};
  for (const ev of events) {
    const date = formatDate(ev.occurred_at);
    if (!grouped[date]) grouped[date] = [];
    grouped[date].push(ev);
  }

  return (
    <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-5 hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20 shadow-[0_0_12px_rgba(34,211,238,0.15)]">
            <Calendar className="w-4.5 h-4.5 text-cyan-400" />
          </div>
          <div className="text-left">
            <h3 className="text-base font-bold text-slate-100">Clinical Timeline</h3>
            <span className="text-xs text-slate-500">{events.length} events</span>
          </div>
        </div>
        <ChevronDown className={`w-5 h-5 text-slate-500 transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-6 max-h-[450px] overflow-y-auto chat-scrollbar pr-3">
          {Object.entries(grouped).map(([date, dayEvents]) => (
            <div key={date}>
              {/* Date Header */}
              <div className="flex items-center gap-3 mb-3">
                <div className="text-xs font-bold text-cyan-400/70 uppercase tracking-widest whitespace-nowrap">{date}</div>
                <div className="flex-1 h-px bg-gradient-to-r from-cyan-500/20 to-transparent" />
              </div>

              {/* Events */}
              <div className="space-y-2 ml-2 border-l border-slate-800 pl-4">
                {dayEvents.map((ev: any) => {
                  const cfg = EVENT_CONFIG[ev.event_type] || EVENT_CONFIG.note;
                  const Icon = cfg.icon;

                  return (
                    <div
                      key={ev.event_id}
                      className={`relative flex items-start gap-3 p-3 rounded-xl ${cfg.bg} border ${cfg.border} hover:bg-white/[0.03] transition-all group`}
                    >
                      {/* Connector dot */}
                      <div className={`absolute -left-[21px] top-4 w-2.5 h-2.5 rounded-full ${cfg.bg} border-2 ${cfg.border} shadow-sm`} />

                      <div className={`w-8 h-8 rounded-lg ${cfg.bg} flex items-center justify-center shrink-0 border ${cfg.border}`}>
                        <Icon className={`w-4 h-4 ${cfg.color}`} />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="text-sm font-semibold text-slate-200 truncate">{ev.title}</h4>
                          <span className="text-[10px] text-slate-500 font-mono shrink-0">{formatTime(ev.occurred_at)}</span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{ev.summary}</p>

                        {ev.citations && ev.citations.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {ev.citations.map((cit: any, cIdx: number) => (
                              <button
                                key={`${cit.citation_id || cit.evidence_id || 'cit'}-${cIdx}`}
                                onClick={() => handleCitationClick(cit)}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-slate-800/50 hover:bg-cyan-900/40 text-[10px] text-cyan-400 border border-slate-700/50 hover:border-cyan-500/40 rounded transition-all"
                                title="View evidence"
                              >
                                {getCitationLabel(cit)}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
