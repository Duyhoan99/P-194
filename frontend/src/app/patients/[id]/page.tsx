'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { auth, patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import StructuredReview from '@/components/StructuredReview';
import ChatPanel from '@/components/ChatPanel';
import EvidencePanel from '@/components/EvidencePanel';
import PatientMetricsChart from '@/components/PatientMetricsChart';
import PatientAlerts from '@/components/PatientAlerts';
import MedicationTimeline from '@/components/MedicationTimeline';
import DataConflictsPanel from '@/components/DataConflictsPanel';
import {
  Activity,
  Clock,
  ShieldAlert,
  Brain,
  X,
  AlertTriangle,
  FileText,
  TrendingUp,
  Pill,
  SplitSquareVertical,
  Bot,
  GripVertical
} from 'lucide-react';
import { motion } from 'framer-motion';

type WorkspaceTab = 'review' | 'medications' | 'conflicts' | 'metrics';

export default function PatientWorkspace() {
  const router = useRouter();
  const params = useParams();
  const patientId = params.id as string;
  const { selectedPatient, setSelectedPatient, clearPatientState, currentReview } = useAppStore();
  const [authChecking, setAuthChecking] = useState(true);
  const [patientData, setPatientData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('review');
  const [showChat, setShowChat] = useState(true);

  // Patient Memory modal
  const [showMemory, setShowMemory] = useState(false);
  const [memory, setMemory] = useState<any>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryError, setMemoryError] = useState('');

  // Authentication check
  useEffect(() => {
    auth.me().then(() => {
      setAuthChecking(false);
    }).catch(() => {
      router.push('/login');
    });
  }, [router]);

  // Load patient overview
  const loadPatientOverview = useCallback(async () => {
    try {
      const list = await patients.list({ search: patientId });
      const pt = list.items?.find((p: any) => p.patient_id === patientId);
      if (pt) {
        setPatientData(pt);
        setSelectedPatient(pt);
      }
    } catch {
      // silently handle
    }
  }, [patientId, setSelectedPatient]);

  useEffect(() => {
    loadPatientOverview();
    return () => {
      clearPatientState();
    };
  }, [patientId, loadPatientOverview, clearPatientState]);

  // Load patient memory
  const handleOpenMemory = async () => {
    setShowMemory(true);
    setMemoryLoading(true);
    setMemoryError('');
    try {
      const mem = await patients.getMemory(patientId);
      setMemory(mem);
    } catch (err: any) {
      setMemoryError(err.detail || 'Chưa có bộ nhớ lâm sàng đã phê duyệt cho bệnh nhân này.');
      setMemory(null);
    } finally {
      setMemoryLoading(false);
    }
  };

  if (authChecking) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-teal-400">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-teal-500/30 border-t-teal-400 rounded-full animate-spin" />
          Đang tải không gian làm việc lâm sàng...
        </div>
      </div>
    );
  }

  const pData = patientData || selectedPatient;
  const conflictCount = currentReview?.conflicts?.length || 0;

  return (
    <div className="flex h-full overflow-hidden bg-transparent">

      {/* Center Workspace */}
      <div className="flex-1 flex flex-col overflow-hidden relative">

        {/* Patient Header */}
        <header className="px-6 py-3.5 border-b border-white/10 clinical-card sticky top-0 z-10 rounded-2xl">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-300 font-bold shadow-inner">
                {pData?.pseudonym ? pData.pseudonym.charAt(0) : 'P'}
              </div>
              <div>
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                    {pData?.pseudonym || patientId}
                  </h2>
                  {pData?.age && (
                    <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium border border-slate-200 dark:border-slate-700">
                      {pData.age} tuổi • {pData.sex === 'male' ? '♂ Nam' : pData.sex === 'female' ? '♀ Nữ' : pData.sex}
                    </span>
                  )}
                  <span className="px-2.5 py-0.5 rounded-full bg-teal-950/80 text-teal-300 text-xs font-mono font-medium border border-teal-800/60 flex items-center gap-1 shadow-sm">
                    <ShieldAlert className="w-3 h-3 text-teal-400" /> {patientId}
                  </span>
                </div>

                <div className="flex items-center gap-3 mt-1 text-xs text-slate-400 flex-wrap">
                  {pData?.primary_condition && (
                    <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 font-medium">
                      <Activity className="w-3.5 h-3.5 text-rose-400" /> {pData.primary_condition}
                    </span>
                  )}
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    Tái khám gần nhất: {pData?.last_encounter_at
                      ? new Date(pData.last_encounter_at).toLocaleDateString('vi-VN')
                      : 'Chưa có dữ liệu'}
                  </span>
                  {pData?.latest_data_watermark && (
                    <span className="font-mono bg-slate-100 dark:bg-slate-900 px-1.5 py-0.5 rounded text-[11px] text-slate-400 border border-slate-200 dark:border-slate-800">
                      WM: {pData.latest_data_watermark}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleOpenMemory}
                className="px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-purple-300 hover:text-purple-200 text-xs font-medium rounded-xl border border-purple-500/30 transition-all shadow-sm flex items-center gap-2"
                title="Xem bộ nhớ lâm sàng đã được phê duyệt"
              >
                <Brain className="w-3.5 h-3.5 text-purple-400" />
                <span>Patient Memory</span>
              </button>
            </div>
          </div>
        </header>

        {/* Workspace 2-Column Responsive Layout */}
        <div className="flex-1 overflow-hidden p-4 sm:p-5 bg-transparent">
          <div className="h-full max-w-[1700px] mx-auto grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">

            {/* LEFT COLUMN: Clinical Workspace with 4 Core Medical Tabs (Expands to 12 cols when Chat is closed!) */}
            <div className={`${showChat ? 'lg:col-span-5' : 'lg:col-span-12'} flex flex-col h-full overflow-hidden gap-3 min-w-0 transition-all duration-300`}>

              {/* Navigation Tabs Bar - 4 High-Value Clinical Tabs */}
              <div className="shrink-0 flex items-center justify-between clinical-card p-1.5 rounded-2xl">
                <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none w-full">
                  <button
                    onClick={() => setActiveTab('review')}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 whitespace-nowrap ${activeTab === 'review'
                      ? 'bg-teal-600 text-white font-bold shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 font-medium'
                      }`}
                  >
                    <FileText className="w-3.5 h-3.5 text-teal-400" />
                    <span>Tóm tắt Lâm sàng</span>
                    {currentReview && (
                      <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono uppercase font-bold ${currentReview.status === 'approved'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        }`}>
                        {currentReview.status || 'DRAFT'}
                      </span>
                    )}
                  </button>

                  <button
                    onClick={() => setActiveTab('medications')}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 whitespace-nowrap ${activeTab === 'medications'
                      ? 'bg-purple-600 text-white font-bold shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 font-medium'
                      }`}
                  >
                    <Pill className="w-3.5 h-3.5 text-purple-400" />
                    <span>Tiến trình Thuốc</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('conflicts')}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 whitespace-nowrap ${activeTab === 'conflicts'
                      ? 'bg-amber-600 text-white font-bold shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 font-medium'
                      }`}
                  >
                    <SplitSquareVertical className="w-3.5 h-3.5 text-amber-400" />
                    <span>Đối soát Mâu thuẫn</span>
                    {conflictCount > 0 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                        {conflictCount}
                      </span>
                    )}
                  </button>

                  <button
                    onClick={() => setActiveTab('metrics')}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 whitespace-nowrap ${activeTab === 'metrics'
                      ? 'bg-gradient-to-r from-teal-500/20 to-cyan-500/20 text-teal-200 border border-teal-500/40 shadow-[0_0_15px_rgba(20,184,166,0.15)]'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                      }`}
                  >
                    <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Diễn tiến Chỉ số</span>
                  </button>
                </div>
              </div>

              {/* Tab Content Container */}
              <div className="flex-1 min-h-0 overflow-hidden relative">
                {activeTab === 'review' && (
                  <div className="h-full min-h-0">
                    <StructuredReview patientId={patientId} />
                  </div>
                )}
                {activeTab === 'medications' && (
                  <div className="h-full min-h-0">
                    <MedicationTimeline patientId={patientId} />
                  </div>
                )}
                {activeTab === 'conflicts' && (
                  <div className="h-full min-h-0">
                    <DataConflictsPanel />
                  </div>
                )}
                {activeTab === 'metrics' && (
                  <div className="h-full min-h-0 overflow-y-auto chat-scrollbar">
                    <PatientMetricsChart patientId={patientId} />
                  </div>
                )}
              </div>

            </div>

            {/* RIGHT COLUMN: AI Co-pilot Assistant (Shown when showChat is true) */}
            {showChat && (
              <div className="lg:col-span-7 flex flex-col h-full overflow-hidden min-w-0 animate-in fade-in slide-in-from-right-4 duration-200">
                <ChatPanel patientId={patientId} onClose={() => setShowChat(false)} />
              </div>
            )}

          </div>
        </div>

      </div>

      {/* Right Evidence Panel for Citation deep dive */}
      <EvidencePanel />

      {/* Floating Action Button to Reopen AI Co-pilot Chat (Draggable vertically along right edge, positioned initially at TOP) */}
      {!showChat && (
        <motion.div
          drag="y"
          dragMomentum={false}
          dragConstraints={{ top: -10, bottom: 580 }}
          dragElastic={0.05}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          className="fixed top-24 right-6 z-40 touch-none select-none"
        >
          <div className="flex items-center gap-1 p-1 bg-slate-900/95 backdrop-blur-md rounded-full border border-teal-500/50 shadow-[0_4px_30px_rgba(20,184,166,0.5)] hover:border-teal-400 transition-all">
            <div
              className="px-1.5 py-2 cursor-grab active:cursor-grabbing text-teal-400/80 hover:text-teal-300 transition-colors"
              title="Kéo thả để di chuyển nút lên/xuống dọc màn hình"
            >
              <GripVertical className="w-3.5 h-3.5" />
            </div>
            <button
              onClick={() => setShowChat(true)}
              className="flex items-center gap-2.5 px-4 py-2.5 bg-gradient-to-r from-teal-500 via-cyan-500 to-indigo-600 hover:from-teal-400 hover:to-indigo-500 text-white font-bold text-xs rounded-full shadow-md hover:scale-102 transition-all cursor-pointer"
              title="Nhấp để mở Trợ lý AI Co-pilot Lâm sàng"
            >
              <div className="relative">
                <Bot className="w-4 h-4" />
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-emerald-400 rounded-full animate-ping" />
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-emerald-400 rounded-full border-2 border-slate-900" />
              </div>
              <span className="tracking-wide font-extrabold pr-1">Mở AI Co-pilot</span>
            </button>
          </div>
        </motion.div>
      )}

      {/* Patient Memory Modal */}
      {showMemory && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-200 dark:border-slate-700/80 rounded-2xl p-6 max-w-xl w-full mx-4 shadow-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/30">
                  <Brain className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-slate-100 text-base">Patient Memory</h3>
                  <p className="text-xs text-slate-400">Tri thức lâm sàng đã được bác sĩ ký duyệt</p>
                </div>
              </div>
              <button
                onClick={() => setShowMemory(false)}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 chat-scrollbar pr-1">
              {memoryLoading ? (
                <div className="text-center py-10 text-slate-400 text-sm">Đang tải bộ nhớ bệnh nhân...</div>
              ) : memoryError ? (
                <div className="text-center py-8">
                  <AlertTriangle className="w-8 h-8 text-amber-500/50 mx-auto mb-2" />
                  <p className="text-sm text-slate-400">{memoryError}</p>
                </div>
              ) : memory ? (
                <>
                  <div className="flex items-center gap-3 text-xs text-slate-400 mb-2 bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span>Phiên bản: <strong className="text-purple-300">v{memory.version}</strong></span>
                    <span>•</span>
                    <span>Phê duyệt bởi: <strong className="text-slate-200">{memory.approved_by}</strong></span>
                    <span>•</span>
                    <span>{new Date(memory.approved_at).toLocaleString('vi-VN')}</span>
                  </div>
                  {memory.items?.map((item: any) => (
                    <div key={item.item_id} className="p-3.5 bg-slate-950/50 border border-slate-200 dark:border-slate-800/80 rounded-xl">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-purple-400/80 mb-1">
                        {item.category}
                      </div>
                      <div className="text-sm text-slate-200 leading-relaxed">{item.text}</div>
                      {item.citations && item.citations.length > 0 && (
                        <div className="flex gap-1.5 mt-2 flex-wrap">
                          {item.citations.map((c: any) => (
                            <span key={c.citation_id} className="text-[10px] font-mono text-cyan-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                              #{c.citation_id?.split('-').pop()?.substring(0, 6)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </>
              ) : (
                <div className="text-center py-8 text-slate-500 text-sm">Chưa có dữ liệu bộ nhớ.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

