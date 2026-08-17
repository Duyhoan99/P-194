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
import Timeline from '@/components/Timeline';
import { Activity, Clock, ShieldAlert, Brain, X, AlertTriangle, Pill } from 'lucide-react';

export default function PatientWorkspace() {
  const router = useRouter();
  const params = useParams();
  const patientId = params.id as string;
  const { selectedPatient, clearPatientState } = useAppStore();
  const [authChecking, setAuthChecking] = useState(true);
  const [patientData, setPatientData] = useState<any>(null);

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
      }
    } catch {
      // silently handle
    }
  }, [patientId]);

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
      setMemoryError(err.detail || 'No approved memory available for this patient.');
      setMemory(null);
    } finally {
      setMemoryLoading(false);
    }
  };

  if (authChecking) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-cyan-500">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
          Loading workspace...
        </div>
      </div>
    );
  }

  const pData = patientData || selectedPatient;

  return (
    <div className="flex h-full overflow-hidden bg-transparent">
      
      {/* Center Workspace */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Patient Header */}
        <header className="px-6 py-5 border-b border-white/5 bg-slate-900/30 backdrop-blur-2xl sticky top-0 z-10 shadow-lg shadow-black/20">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-slate-100 tracking-tight">
                  {pData?.pseudonym || patientId}
                </h2>
                {pData?.age && (
                  <span className="px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 text-xs font-medium border border-slate-700">
                    {pData.age}y • {pData.sex === 'male' ? '♂ Nam' : pData.sex === 'female' ? '♀ Nữ' : pData.sex}
                  </span>
                )}
                <span className="px-2 py-0.5 rounded-full bg-cyan-900/30 text-cyan-400 text-xs font-medium border border-cyan-800/50 flex items-center gap-1 shadow-sm shadow-cyan-900/20">
                  <ShieldAlert className="w-3 h-3" /> {patientId}
                </span>
              </div>
              
              <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                {pData?.primary_condition && (
                  <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/15 text-rose-400">
                    <Activity className="w-3.5 h-3.5"/> {pData.primary_condition}
                  </span>
                )}
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-slate-500"/>
                  Last updated: {new Date(pData?.last_encounter_at || Date.now()).toLocaleDateString('vi-VN')}
                </span>
                {pData?.latest_data_watermark && (
                  <span className="font-mono bg-slate-800/50 px-1.5 rounded text-[10px] text-slate-500">
                    WM: {pData.latest_data_watermark}
                  </span>
                )}
              </div>
            </div>
            
            <div className="flex gap-2">
              <button 
                onClick={handleOpenMemory}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg border border-slate-700 transition-colors shadow-sm flex items-center gap-2"
              >
                <Brain className="w-4 h-4 text-purple-400" />
                Patient Memory
              </button>
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 scroll-smooth bg-transparent">
          <div className="max-w-[1440px] w-full mx-auto flex flex-col gap-6 min-h-[750px]">
            
            <PatientAlerts />
            <PatientMetricsChart patientId={patientId} />
            <Timeline patientId={patientId} />

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 pb-12 items-start">
              <div className="w-full min-w-0 h-[840px]">
                <StructuredReview patientId={patientId} />
              </div>
              <div className="w-full min-w-0 h-[840px]">
                <ChatPanel patientId={patientId} />
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Right Evidence Panel */}
      <EvidencePanel />

      {/* Patient Memory Modal */}
      {showMemory && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-xl w-full mx-4 shadow-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-purple-500/10 flex items-center justify-center border border-purple-500/20">
                  <Brain className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-100">Patient Memory</h3>
                  <p className="text-xs text-slate-400">Approved clinical knowledge base</p>
                </div>
              </div>
              <button onClick={() => setShowMemory(false)} className="p-1 text-slate-400 hover:text-white rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3">
              {memoryLoading ? (
                <div className="text-center py-8 text-slate-500 text-sm">Loading memory...</div>
              ) : memoryError ? (
                <div className="text-center py-8">
                  <AlertTriangle className="w-8 h-8 text-amber-500/50 mx-auto mb-2" />
                  <p className="text-sm text-slate-400">{memoryError}</p>
                </div>
              ) : memory ? (
                <>
                  <div className="flex items-center gap-3 text-xs text-slate-500 mb-2">
                    <span>Version {memory.version}</span>
                    <span>•</span>
                    <span>Approved by {memory.approved_by}</span>
                    <span>•</span>
                    <span>{new Date(memory.approved_at).toLocaleString()}</span>
                  </div>
                  {memory.items?.map((item: any) => (
                    <div key={item.item_id} className="p-3 bg-slate-800/30 border border-slate-700/50 rounded-lg">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-purple-400/70 mb-1">
                        {item.category}
                      </div>
                      <div className="text-sm text-slate-300">{item.text}</div>
                      {item.citations && item.citations.length > 0 && (
                        <div className="flex gap-1 mt-2">
                          {item.citations.map((c: any) => (
                            <span key={c.citation_id} className="text-[10px] font-mono text-cyan-500 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
                              {c.citation_id?.split('-').pop()?.substring(0, 4)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </>
              ) : (
                <div className="text-center py-8 text-slate-500 text-sm">No memory data.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
