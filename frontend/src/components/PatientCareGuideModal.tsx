'use client';

import React, { useCallback, useState, useEffect, useRef } from 'react';
import { patients, type CarePlanDataSummary, type ClinicalBasisItem } from '@/lib/api';
import {
  HeartPulse,
  Pill,
  Apple,
  Footprints,
  AlertOctagon,
  Download,
  Volume2,
  VolumeX,
  X,
  CheckCircle2,
  PhoneCall,
  Edit3,
  Save,
  RotateCcw,
  Stethoscope,
  BookOpen,
  ChevronUp,
  UserCheck,
  Sparkles
} from 'lucide-react';

interface PatientCareGuideModalProps {
  patient?: any;
  patientId?: string;
  review?: any;
  isOpen: boolean;
  onClose: () => void;
}

export default function PatientCareGuideModal({
  patient,
  patientId: propPatientId,
  review,
  isOpen,
  onClose
}: PatientCareGuideModalProps) {
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [currentSentenceIdx, setCurrentSentenceIdx] = useState<number>(-1);
  const [isEditing, setIsEditing] = useState(false);
  const [showGuidelines, setShowGuidelines] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Robust multi-source resolution for current patient
  const [fetchedPatient, setFetchedPatient] = useState<any>(null);

  const effectivePatientId = propPatientId || patient?.patient_id || '';

  useEffect(() => {
    if (isOpen && effectivePatientId) {
      fetch(`/api/v1/patients?search=${effectivePatientId}`)
        .then(r => r.json())
        .then(data => {
          const pt = data?.items?.find((p: any) => p.patient_id === effectivePatientId);
          if (pt) setFetchedPatient(pt);
        })
        .catch(() => {});
    }
  }, [effectivePatientId, isOpen]);

  const activePt = fetchedPatient || (patient?.patient_id === effectivePatientId ? patient : null);

  const patientName = activePt?.pseudonym || patient?.pseudonym || 'Bệnh nhân';
  const age = activePt?.age ?? patient?.age ?? 'Chưa rõ';
  const gender = activePt?.sex === 'female' ? 'Nữ' : activePt?.sex === 'male' ? 'Nam' : 'Chưa rõ';
  const patientId = effectivePatientId;
  const lastEncounter = activePt?.last_encounter_at 
    ? new Date(activePt.last_encounter_at).toLocaleDateString('vi-VN') 
    : new Date().toLocaleDateString('vi-VN');

  // Doctor & Guideline Grounded Fields (Dynamic based on patient condition & medications)
  const [doctorGreeting, setDoctorGreeting] = useState('');
  const [personalizationSummary, setPersonalizationSummary] = useState('');
  const [medicationNeed, setMedicationNeed] = useState<'yes' | 'no' | 'undetermined'>('undetermined');
  const [medicationAssessment, setMedicationAssessment] = useState('');
  const [medicationRecommendation, setMedicationRecommendation] = useState('');
  const [morningMeds, setMorningMeds] = useState('');
  const [eveningMeds, setEveningMeds] = useState('');
  const [medicationNote, setMedicationNote] = useState('');
  const [dietGood, setDietGood] = useState('');
  const [dietBad, setDietBad] = useState('');
  const [exercise, setExercise] = useState('');
  const [warning, setWarning] = useState('');
  const [followUp, setFollowUp] = useState('Tái khám theo lịch được bác sĩ xác nhận.');
  const [doctorSignName, setDoctorSignName] = useState('Chưa ký duyệt');
  const [isGeneratingLLM, setIsGeneratingLLM] = useState(false);
  const [agentBadge, setAgentBadge] = useState('Agent hỗ trợ bệnh lý');
  const [generationMode, setGenerationMode] = useState('deterministic_grounded');
  const [requiresReview, setRequiresReview] = useState(true);
  const [safetyFlags, setSafetyFlags] = useState<string[]>([]);
  const [guidelineCitations, setGuidelineCitations] = useState<string[]>([]);
  const [clinicalBasis, setClinicalBasis] = useState<ClinicalBasisItem[]>([]);
  const [dataSummary, setDataSummary] = useState<CarePlanDataSummary>({ conditions: [], medications: [], latest_observations: [], allergies: [], conflicts: [] });
  const [disclaimer, setDisclaimer] = useState('Bản nháp cần bác sĩ kiểm tra và phê duyệt trước khi sử dụng.');
  const [generationError, setGenerationError] = useState('');
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  const condition = dataSummary.conditions?.length
    ? dataSummary.conditions.join(', ')
    : activePt?.primary_condition || patient?.primary_condition || 'Chưa có chẩn đoán được xác minh';

  // Call Live Clinical LLM Agent with Medical RAG & Guardrails
  const handleGenerateWithLLMAgent = useCallback(async () => {
    setIsGeneratingLLM(true);
    setGenerationError('');
    if (!patientId) {
      setGenerationError('Chưa chọn bệnh nhân để tạo bản nháp chăm sóc.');
      setIsGeneratingLLM(false);
      return;
    }
    if (review?.status !== 'approved') {
      setGenerationError('Cần xử lý các điểm chưa xác minh và ký duyệt bản tóm tắt trước khi tạo phác đồ.');
      setIsGeneratingLLM(false);
      return;
    }
    try {
      const data = await patients.generateCarePlan(patientId);
      if (data.plan) {
        const p = data.plan;
        setDoctorGreeting(p.doctor_greeting || '');
        setPersonalizationSummary(p.personalization_summary || '');
        setMedicationNeed(p.medication_need || 'undetermined');
        setMedicationAssessment(p.medication_assessment || '');
        setMedicationRecommendation(p.medication_recommendation || '');
        setMorningMeds(p.morning_meds || '');
        setEveningMeds(p.evening_meds || '');
        setMedicationNote(p.medication_note || '');
        setDietGood(p.diet_good || '');
        setDietBad(p.diet_bad || '');
        setExercise(p.exercise || '');
        setWarning(p.emergency_warning || '');
        setFollowUp(p.follow_up || 'Tái khám theo lịch được bác sĩ xác nhận.');
      }
      setAgentBadge(data.agent_type || 'Agent hỗ trợ bệnh lý');
      setGenerationMode(data.generation_mode || 'deterministic_grounded');
      setRequiresReview(data.requires_clinician_review !== false);
      setSafetyFlags(data.safety_flags || []);
      setGuidelineCitations(data.guideline_citations || []);
      setClinicalBasis(data.clinical_basis || []);
      setDataSummary(data.data_summary || { conditions: [], medications: [], latest_observations: [], allergies: [], conflicts: [] });
      setDisclaimer(data.disclaimer || 'Bản nháp cần bác sĩ kiểm tra và phê duyệt trước khi sử dụng.');
    } catch (e: unknown) {
      console.warn('Care Plan Agent unavailable:', e);
      setGenerationError(e instanceof Error ? e.message : 'Không thể tạo bản nháp từ hồ sơ hiện tại.');
    } finally {
      setIsGeneratingLLM(false);
    }
  }, [patientId, review?.status]);

  // Synchronize when patient or modal opens
  useEffect(() => {
    if (isOpen) {
      handleGenerateWithLLMAgent();
    }
  }, [isOpen, effectivePatientId, handleGenerateWithLLMAgent]);

  // Dynamic sentence list generated from the active text (Covers 100% of all sections)
  const getDynamicSentences = () => {
    const list: string[] = [];
    
    // 1. Lời mở đầu & Lời chào bác sĩ
    list.push(`Chào bác ${patientName}. Đây là bản hướng dẫn dự thảo đã được cá nhân hóa từ hồ sơ hiện tại.`);
    if (doctorGreeting) list.push(doctorGreeting);

    // 2. Lịch uống thuốc chi tiết
    list.push(`Thứ nhất, về thuốc đang được ghi nhận: Lần dùng thứ nhất: ${morningMeds}.`);
    list.push(`Lần dùng thứ hai: ${eveningMeds}. ${medicationNote}`);

    // 3. Chế độ ăn uống & kiêng cữ
    list.push(`Thứ hai, về chế độ dinh dưỡng: Bác nên ăn và tăng cường: ${dietGood}`);
    list.push(`Đồng thời, bác cần kiêng cữ và hạn chế: ${dietBad}`);

    // 4. Vận động & thói quen sinh hoạt
    list.push(`Thứ ba, về vận động và chăm sóc thân thể: ${exercise}`);

    // 5. Cảnh báo cấp cứu & xử trí khẩn cấp
    list.push(`Thứ tư, điều đặc biệt lưu ý khi có dấu hiệu cấp cứu: ${warning}`);

    // 6. Lịch tái khám & Hotline hỗ trợ
    list.push(`${followUp} Khi cần hỗ trợ y tế khẩn cấp, người nhà vui lòng gọi 115.`);
    list.push(`Kính chúc bác ${patientName} luôn dồi dào sức khỏe và bình an!`);

    return list.filter(s => s && s.trim().length > 0);
  };

  // Cleanup audio
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  const playSentencesWithAudio = (index: number, sentencesList: string[]) => {
    if (index >= sentencesList.length) {
      setIsPlayingAudio(false);
      setCurrentSentenceIdx(-1);
      return;
    }

    setCurrentSentenceIdx(index);
    const text = sentencesList[index];
    const encodedText = encodeURIComponent(text);
    const audioUrl = `/tts-stream?text=${encodedText}`;

    if (!audioRef.current) {
      audioRef.current = new Audio();
    }

    audioRef.current.src = audioUrl;
    audioRef.current.playbackRate = 1.0;

    audioRef.current.onended = () => {
      setTimeout(() => {
        playSentencesWithAudio(index + 1, sentencesList);
      }, 250);
    };

    audioRef.current.onerror = () => {
      setTimeout(() => {
        playSentencesWithAudio(index + 1, sentencesList);
      }, 250);
    };

    audioRef.current.play().catch(() => {
      setIsPlayingAudio(false);
      setCurrentSentenceIdx(-1);
    });
  };

  const handleToggleSpeech = () => {
    if (isPlayingAudio) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      setIsPlayingAudio(false);
      setCurrentSentenceIdx(-1);
    } else {
      setIsPlayingAudio(true);
      const dynamicList = getDynamicSentences();
      playSentencesWithAudio(0, dynamicList);
    }
  };

  const handleExportPdf = async () => {
    if (!patientId || isExportingPdf) return;
    if (requiresReview) {
      setGenerationError('Bác sĩ cần hoàn tất hiệu chỉnh, ghi tên và bấm “Ký duyệt lời dặn” trước khi xuất PDF có mã QR.');
      return;
    }
    setIsExportingPdf(true);
    setGenerationError('');
    try {
      const blob = await patients.exportCarePlanPdf(patientId, {
        plan: {
          doctor_greeting: doctorGreeting,
          personalization_summary: personalizationSummary,
          medication_need: medicationNeed,
          medication_assessment: medicationAssessment,
          medication_recommendation: medicationRecommendation,
          medication_basis_ids: clinicalBasis.filter(item => item.applies_to.includes('medication')).map(item => item.basis_id),
          morning_meds: morningMeds,
          evening_meds: eveningMeds,
          medication_note: medicationNote,
          diet_good: dietGood,
          diet_bad: dietBad,
          diet_basis_ids: clinicalBasis.filter(item => item.applies_to.includes('diet')).map(item => item.basis_id),
          exercise,
          exercise_basis_ids: clinicalBasis.filter(item => item.applies_to.includes('exercise')).map(item => item.basis_id),
          emergency_warning: warning,
          warning_basis_ids: clinicalBasis.filter(item => item.applies_to.includes('warning')).map(item => item.basis_id),
          follow_up: followUp,
          follow_up_days: null,
          guideline_citation: guidelineCitations[0] || '',
        },
        data_summary: dataSummary,
        doctor_sign_name: doctorSignName,
      });
      const downloadUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = downloadUrl;
      anchor.download = `Huong_dan_dieu_tri_${patientId}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (error: unknown) {
      setGenerationError(error instanceof Error ? error.message : 'Không thể xuất file PDF hướng dẫn điều trị.');
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleResetDefaults = () => {
    void handleGenerateWithLLMAgent();
  };

  const handleToggleEdit = () => {
    if (!isEditing) {
      setRequiresReview(true);
      setGenerationError('');
      setIsEditing(true);
      return;
    }
    const signer = doctorSignName.trim().toLocaleLowerCase('vi-VN');
    if (!signer || signer === 'chưa ký duyệt' || signer === 'chưa xác nhận') {
      setGenerationError('Bác sĩ cần ghi rõ tên người ký duyệt trước khi phát hành hướng dẫn cho bệnh nhân.');
      return;
    }
    setRequiresReview(false);
    setGenerationError('');
    setIsEditing(false);
  };

  if (!isOpen) return null;

  const currentSentences = getDynamicSentences();

  return (
    <>
      {/* Embedded Print CSS for authentic medical A4 printout */}
      <style jsx global>{`
        @page {
          size: A4 portrait;
          margin: 11mm 12mm 13mm;
        }

        @media print {
          html,
          body {
            width: auto !important;
            min-width: 0 !important;
            height: auto !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: visible !important;
            background: #ffffff !important;
          }
          *,
          *::before,
          *::after {
            box-sizing: border-box !important;
          }
          body * {
            visibility: hidden !important;
          }
          body *:not(:has(#patient-guide-print-shell)):not(#patient-guide-print-shell):not(#patient-guide-print-shell *) {
            display: none !important;
          }
          body *:has(#patient-guide-print-shell) {
            position: static !important;
            inset: auto !important;
            display: block !important;
            width: auto !important;
            min-width: 0 !important;
            height: auto !important;
            min-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: visible !important;
            transform: none !important;
          }
          #patient-guide-print-shell,
          #patient-guide-print-shell * {
            visibility: visible !important;
          }
          #patient-guide-print-shell {
            position: static !important;
            inset: auto !important;
            display: block !important;
            width: 100% !important;
            min-width: 0 !important;
            height: auto !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: visible !important;
            background: #ffffff !important;
            backdrop-filter: none !important;
          }
          #printable-patient-guide,
          #printable-patient-guide * {
            visibility: visible !important;
          }
          #printable-patient-guide {
            position: static !important;
            inset: auto !important;
            width: 100% !important;
            min-width: 0 !important;
            max-width: none !important;
            height: auto !important;
            max-height: none !important;
            overflow: visible !important;
            background: #ffffff !important;
            color: #0f172a !important;
            padding: 0 !important;
            margin: 0 !important;
            border: none !important;
            box-shadow: none !important;
            font-family: 'Times New Roman', Times, serif !important;
            font-size: 9.5pt !important;
            line-height: 1.35 !important;
            print-color-adjust: exact !important;
            -webkit-print-color-adjust: exact !important;
          }
          .no-print {
            display: none !important;
          }
          .care-print-header {
            margin: 0 0 5mm !important;
            padding: 0 0 3mm !important;
            break-inside: avoid !important;
          }
          .care-print-header h1 {
            margin: 3mm 0 1mm !important;
            font-size: 16pt !important;
            line-height: 1.2 !important;
            letter-spacing: 0 !important;
          }
          .care-print-patient-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 2mm 6mm !important;
            margin-top: 3mm !important;
            padding: 3mm !important;
          }
          .care-print-patient-grid > div,
          .care-print-card,
          .care-print-card * {
            min-width: 0 !important;
            overflow-wrap: anywhere !important;
          }
          .care-print-content {
            display: block !important;
            width: 100% !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            overflow: visible !important;
          }
          .care-print-intro {
            break-inside: avoid !important;
            box-shadow: none !important;
          }
          .care-print-sections {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            align-items: start !important;
            gap: 4mm !important;
            width: 100% !important;
            min-width: 0 !important;
          }
          .care-print-card {
            width: 100% !important;
            padding: 4mm !important;
            border-color: #cbd5e1 !important;
            border-radius: 2mm !important;
            box-shadow: none !important;
            break-inside: avoid !important;
            page-break-inside: avoid !important;
          }
          .care-print-footer {
            margin-top: 8mm !important;
            padding-top: 4mm !important;
            break-inside: avoid !important;
            page-break-inside: avoid !important;
          }
        }
      `}</style>

      {/* Screen Modal Backdrop */}
      <div id="patient-guide-print-shell" className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 p-2 sm:p-4 animate-in fade-in duration-150">
        <div 
          id="printable-patient-guide"
          className="bg-slate-900 border border-slate-700/80 rounded-3xl max-w-4xl w-full max-h-[94vh] flex flex-col shadow-2xl overflow-hidden print:max-w-none print:max-h-none print:rounded-none"
        >
          
          {/* 1. Modal Top Bar (Screen only - Clean structured 2-row layout to prevent clipping) */}
          <div className="no-print p-4 sm:px-6 border-b border-white/10 bg-slate-950/95 shrink-0 space-y-3">
            {/* Top Row: Title + Close Button */}
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-teal-500/20 to-cyan-500/20 border border-teal-500/30 flex items-center justify-center text-teal-300 shrink-0 shadow-inner">
                  <HeartPulse className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-base sm:text-lg font-bold text-slate-100">
                      Phiếu Hướng Dẫn Điều Trị &amp; Chăm Sóc Tại Nhà
                    </h3>
                    <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                      <UserCheck className="w-3.5 h-3.5 text-amber-400" />
                      {requiresReview ? 'Bản nháp — Chưa phê duyệt' : `Đã duyệt bởi ${doctorSignName}`}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Hồ sơ: <strong className="text-slate-200">{patientName}</strong> ({age} tuổi • {gender}) • <span className="text-teal-300">{condition}</span>
                  </p>
                </div>
              </div>

              {/* Close Button */}
              <button
                onClick={onClose}
                className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors shrink-0"
                title="Đóng cửa sổ"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Bottom Row: Quick Action Toolbar */}
            <div className="flex items-center justify-between gap-2 pt-1 border-t border-slate-800/80 flex-wrap">
              <div className="text-[11px] text-slate-400 flex items-center gap-1.5 flex-wrap">
                <span className="px-2 py-0.5 rounded-md bg-purple-500/15 text-purple-300 border border-purple-500/30 text-[10px] font-bold flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-purple-400" /> {agentBadge}
                </span>
                <span className="text-slate-500">•</span>
                <span>Chế độ: <strong>{generationMode === 'llm_grounded' ? 'Mô hình ngôn ngữ có căn cứ' : 'Luật xác định có căn cứ'}</strong></span>
                {clinicalBasis.length > 0 && (
                  <><span className="text-slate-500">•</span><span>{clinicalBasis.length} căn cứ áp dụng cho ca bệnh</span></>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* AI Agent Re-generate Button */}
                <button
                  onClick={handleGenerateWithLLMAgent}
                  disabled={isGeneratingLLM}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl transition-all border bg-gradient-to-r from-purple-900/60 to-indigo-900/60 hover:from-purple-800/80 hover:to-indigo-800/80 text-purple-200 border-purple-500/40 shadow-sm disabled:opacity-50"
                  title="Tạo lại bản nháp từ dữ liệu FHIR và bằng chứng của đúng bệnh nhân"
                >
                  <Sparkles className={`w-3.5 h-3.5 text-purple-300 ${isGeneratingLLM ? 'animate-spin' : ''}`} />
                  <span>{isGeneratingLLM ? 'Đang đọc hồ sơ...' : 'Tạo lại từ hồ sơ'}</span>
                </button>

                {/* MOH Guideline Reference Button */}
                <button
                  onClick={() => setShowGuidelines(!showGuidelines)}
                  aria-expanded={showGuidelines}
                  aria-controls="care-plan-evidence-panel"
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl transition-all border ${
                    showGuidelines
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm'
                      : 'bg-slate-800/90 hover:bg-slate-700 text-amber-300/90 border-slate-700'
                  }`}
                  title="Chỉ mở phần tra cứu căn cứ trên màn hình; căn cứ không được đưa vào PDF"
                >
                  <BookOpen className="w-3.5 h-3.5 text-amber-400" />
                  <span>{showGuidelines ? 'Ẩn căn cứ' : 'Xem căn cứ'}</span>
                </button>

                {/* Doctor Edit Toggle Button */}
                <button
                  onClick={handleToggleEdit}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl transition-all shadow-sm ${
                    isEditing
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                      : 'bg-slate-800 hover:bg-slate-700 text-cyan-300 hover:text-cyan-200 border border-slate-700'
                  }`}
                  title="Bác sĩ bấm vào đây để tự tay chỉnh sửa nội dung dặn dò"
                >
                  {isEditing ? (
                    <>
                      <Save className="w-3.5 h-3.5" />
                      <span>Ký duyệt lời dặn</span>
                    </>
                  ) : (
                    <>
                      <Edit3 className="w-3.5 h-3.5" />
                      <span>Bác sĩ tùy biến</span>
                    </>
                  )}
                </button>

                {/* Print Button */}
                <button
                  onClick={handleExportPdf}
                  disabled={isExportingPdf || requiresReview}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-teal-950/40 disabled:opacity-50"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{isExportingPdf ? 'Đang tạo PDF...' : 'Xuất PDF'}</span>
                </button>
              </div>
            </div>
          </div>

          {/* 2. PRINT-ONLY HEADER (Chỉ hiện khi in ra giấy A4) */}
          <div className="care-print-header hidden print:block mb-4 pb-3 border-b-2 border-slate-800">
            <div className="flex justify-between items-start">
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-slate-600">SỞ Y TẾ TP. HỒ CHÍ MINH</div>
                <div className="text-sm font-bold uppercase text-slate-900">PHÒNG KHÁM ĐA KHOA KỸ THUẬT CAO P-194</div>
                <div className="text-[10pt] text-slate-500 italic">Địa chỉ: 123 Nguyễn Huệ, Quận 1 • Hotline: 1900 8888</div>
              </div>
              <div className="text-right">
                <div className="text-[10pt] font-bold text-slate-900">Mã BN: {patientId}</div>
                <div className="text-[9pt] text-slate-500">Ngày in: {new Date().toLocaleDateString('vi-VN')}</div>
              </div>
            </div>

            <div className="text-center mt-3 pt-2">
              <h1 className="text-lg font-bold uppercase tracking-wide text-slate-900">
                PHIẾU HƯỚNG DẪN ĐIỀU TRỊ &amp; DẶN DÒ TẠI NHÀ
              </h1>
              <p className="text-[10pt] text-slate-600 italic">
                (BẢN NHÁP HỖ TRỢ LÂM SÀNG — cần bác sĩ kiểm tra và ký duyệt trước khi phát hành)
              </p>
            </div>

            {/* Patient Info Row in Print */}
            <div className="care-print-patient-grid grid grid-cols-4 gap-2 mt-3 p-2 bg-slate-50 border border-slate-300 rounded text-[10pt]">
              <div>Họ tên: <strong>{patientName}</strong></div>
              <div>Tuổi / Giới: <strong>{age} tuổi ({gender})</strong></div>
              <div>Ngày khám: <strong>{lastEncounter}</strong></div>
              <div>Chẩn đoán: <strong>{condition}</strong></div>
            </div>
          </div>

          {/* 3. Main Scrollable Content */}
          <div className="care-print-content flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-5 chat-scrollbar bg-slate-950/40 print:p-0 print:space-y-4 print:bg-white print:overflow-visible">
            
            {/* Notification when in edit mode */}
            {isEditing && (
              <div className="no-print bg-cyan-950/40 border border-cyan-500/40 p-3 rounded-2xl flex items-center justify-between text-xs text-cyan-200">
                <div className="flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-cyan-400 shrink-0" />
                  <span><strong>Chế độ bác sĩ hiệu chỉnh:</strong> Nội dung chỉnh sửa vẫn là bản nháp cho đến khi có quy trình ký duyệt chính thức.</span>
                </div>
                <button
                  onClick={handleResetDefaults}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 text-[11px] flex items-center gap-1 shrink-0"
                >
                  <RotateCcw className="w-3 h-3" /> Nạp lại từ hồ sơ
                </button>
              </div>
            )}

            {generationError && (
              <div className="no-print bg-rose-950/40 border border-rose-500/40 p-3 rounded-2xl text-xs text-rose-200">
                <strong>Không tạo được bản nháp:</strong> {generationError} Không sử dụng dữ liệu mẫu thay thế.
              </div>
            )}

            {safetyFlags.length > 0 && (
              <div className="bg-amber-950/30 border border-amber-500/40 p-3 rounded-2xl text-xs text-amber-100 print:bg-amber-50 print:text-slate-900 print:border-amber-300">
                <div className="font-bold mb-1.5 flex items-center gap-1.5">
                  <AlertOctagon className="w-4 h-4" /> Cờ an toàn cần bác sĩ rà soát
                </div>
                <ul className="space-y-1 list-disc pl-5">
                  {safetyFlags.map((flag, index) => <li key={`${flag}-${index}`}>{flag}</li>)}
                </ul>
              </div>
            )}

            {/* Patient evidence and guideline provenance */}
            {showGuidelines && (
              <div id="care-plan-evidence-panel" className="no-print bg-slate-900/95 border border-amber-500/40 rounded-2xl p-4 sm:p-5 space-y-4 shadow-xl animate-in fade-in slide-in-from-top-2">
                <div className="flex items-center justify-between border-b border-amber-500/20 pb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                      <BookOpen className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-xs sm:text-sm font-bold text-amber-200 flex items-center gap-2">
                        <span>Dữ liệu cá nhân hóa và căn cứ chuyên môn</span>
                      </h4>
                      <p className="text-[11px] text-slate-400">
                        Chỉ hiển thị dữ liệu thực sự được gửi vào agent; không dùng giá trị demo gán cứng.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setShowGuidelines(false)}
                    className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
                    title="Thu gọn"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-[11px]">
                  <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 space-y-2">
                    <div className="font-bold text-teal-300">Hồ sơ bệnh nhân đã dùng</div>
                    <p><strong>Chẩn đoán:</strong> {dataSummary.conditions?.join('; ') || 'Chưa có dữ liệu'}</p>
                    <p><strong>Thuốc hoạt động:</strong> {dataSummary.medications?.join('; ') || 'Chưa có dữ liệu'}</p>
                    <p><strong>Chỉ số gần nhất:</strong> {dataSummary.latest_observations?.join('; ') || 'Chưa có dữ liệu'}</p>
                    {dataSummary.allergies?.length > 0 && <p><strong>Dị ứng:</strong> {dataSummary.allergies.join('; ')}</p>}
                    {dataSummary.conflicts?.length > 0 && <p className="text-rose-300"><strong>Mâu thuẫn:</strong> {dataSummary.conflicts.join('; ')}</p>}
                  </div>
                  <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 space-y-2">
                    <div className="font-bold text-amber-300">Căn cứ chuyên môn đã áp dụng</div>
                    {clinicalBasis.length > 0 ? (
                      <ol className="space-y-2 text-slate-300">
                        {clinicalBasis.map(item => (
                          <li key={item.basis_id} className="rounded-lg border border-slate-800 bg-slate-900/70 p-2.5">
                            <div className="font-semibold text-slate-100">[{item.basis_id}] {item.source_title}</div>
                            <div className="mt-0.5 text-slate-400">Mục áp dụng: {item.section}</div>
                            <div className="mt-1">{item.applied_content}</div>
                            <div className="mt-1 text-[10px] text-slate-500">Tài liệu: {item.source_reference}</div>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="text-slate-400">Chưa ánh xạ được guideline bệnh-specific; agent chỉ tạo hướng dẫn chung và yêu cầu rà soát.</p>
                    )}
                    <p className="text-slate-400 border-t border-slate-800 pt-2">{disclaimer}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Lời dặn Bác sĩ + Audio Voice Player */}
            <div className="care-print-intro bg-gradient-to-r from-slate-900 via-teal-950/30 to-slate-900 border border-teal-500/30 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-lg print:border print:border-slate-300 print:bg-slate-50 print:p-3 print:rounded-lg">
              <div className="flex items-start gap-3.5 flex-1 w-full">
                <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 shrink-0 mt-0.5 print:hidden">
                  <Stethoscope className="w-5 h-5" />
                </div>
                <div className="space-y-1.5 flex-1 w-full">
                  <div className="text-xs font-bold text-teal-300 uppercase tracking-wider flex items-center justify-between print:text-slate-800">
                    <span>Lời dặn dự thảo để bác sĩ rà soát:</span>
                    <span className="text-[10px] text-slate-400 font-normal no-print">
                      ({generationMode === 'llm_grounded' ? 'Mô hình ngôn ngữ có căn cứ' : 'Luật xác định có căn cứ'})
                    </span>
                  </div>
                  {isEditing ? (
                    <textarea
                      value={doctorGreeting}
                      onChange={(e) => setDoctorGreeting(e.target.value)}
                      className="w-full bg-slate-950 border border-teal-500/50 rounded-xl p-2.5 text-xs sm:text-sm text-slate-100 focus:outline-none focus:border-teal-400 min-h-[70px] resize-y"
                      placeholder="Nhập lời dặn trực tiếp của bác sĩ..."
                    />
                  ) : (
                    <p className="text-xs sm:text-sm text-slate-200 leading-relaxed print:text-slate-800">
                      {`“${doctorGreeting}”`}
                    </p>
                  )}
                  {personalizationSummary && (
                    <p className="text-[11px] leading-relaxed text-teal-200/90 print:text-slate-700">
                      <strong>Trọng tâm cá nhân hóa:</strong> {personalizationSummary}
                    </p>
                  )}
                </div>
              </div>

              {/* Voice Player Button (Screen Only) */}
              {!isEditing && !requiresReview && (
                <div className="no-print shrink-0 w-full sm:w-auto">
                  <button
                    onClick={handleToggleSpeech}
                    className={`w-full sm:w-auto px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-md flex items-center justify-center gap-2 ${
                      isPlayingAudio
                        ? 'bg-rose-600 hover:bg-rose-500 text-white animate-pulse'
                        : 'bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white shadow-teal-950/50'
                    }`}
                  >
                    {isPlayingAudio ? (
                      <>
                        <VolumeX className="w-4 h-4" />
                        <span>Dừng đọc</span>
                      </>
                    ) : (
                      <>
                        <Volume2 className="w-4 h-4" />
                        <span>Nghe hướng dẫn đã duyệt</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>

            {/* Karaoke-Style Sentence Highlight when Audio is playing (Screen only) */}
            {isPlayingAudio && currentSentenceIdx >= 0 && currentSentenceIdx < currentSentences.length && (
              <div className="no-print bg-slate-900/90 border border-teal-500/40 p-3.5 rounded-xl text-xs text-teal-200 font-medium flex items-center gap-2.5 animate-in fade-in">
                <Volume2 className="w-4 h-4 text-teal-400 animate-bounce shrink-0" />
                <span>Đang đọc: <em>{`“${currentSentences[currentSentenceIdx]}”`}</em></span>
              </div>
            )}

            {/* 4 CORE CLINICAL GUIDANCE PILLARS */}
            <div className="care-print-sections grid grid-cols-1 md:grid-cols-2 gap-4 print:grid-cols-2 print:gap-3">
              
              {/* 1. LỊCH UỐNG THUỐC */}
              <div className="care-print-card bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-md print:bg-white print:border print:border-slate-300 print:rounded-lg print:p-3">
                <div className="flex items-center gap-2 text-purple-400 font-bold text-xs uppercase tracking-wider pb-2 border-b border-slate-800 print:text-slate-900 print:border-slate-300">
                  <Pill className="w-4 h-4 text-purple-400 print:text-slate-800" />
                  <span>1. Thuốc đang hoạt động trong hồ sơ</span>
                </div>

                <div className={`rounded-xl border p-3 text-xs ${
                  medicationNeed === 'yes'
                    ? 'bg-emerald-950/25 border-emerald-700/40 text-emerald-100'
                    : medicationNeed === 'no'
                      ? 'bg-slate-950/70 border-slate-700 text-slate-200'
                      : 'bg-amber-950/25 border-amber-700/40 text-amber-100'
                } print:bg-white print:text-slate-900 print:border-slate-300`}>
                  <div className="font-bold mb-1">
                    Có cần điều trị bằng thuốc? {medicationNeed === 'yes' ? 'CÓ' : medicationNeed === 'no' ? 'KHÔNG' : 'CHƯA KẾT LUẬN'}
                  </div>
                  <p className="leading-relaxed">{medicationAssessment}</p>
                </div>

                {dataSummary.medications?.length > 0 && (
                  <div className="rounded-xl border border-slate-700/80 bg-slate-950/70 p-3 print:bg-white print:border-slate-300">
                    <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400 mb-2 print:text-slate-700">
                      Thuốc đang được ghi nhận
                    </div>
                    <ul className="space-y-1.5 text-xs font-semibold text-slate-100 print:text-slate-900">
                      {dataSummary.medications.map((medication) => (
                        <li key={medication} className="flex items-start gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 text-teal-400 shrink-0 print:text-slate-700" />
                          <span>{medication}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {medicationRecommendation && (
                  <div className="rounded-xl border border-purple-500/30 bg-purple-950/20 p-3 text-[11px] leading-relaxed text-purple-100 print:bg-white print:text-slate-900 print:border-slate-300">
                    {medicationRecommendation}
                  </div>
                )}

                {isEditing ? (
                  <div className="space-y-2.5">
                    <div>
                      <label className="text-[11px] font-bold text-amber-400 block mb-1">Lần dùng 1 / buổi sáng nếu đơn ghi rõ:</label>
                      <input
                        type="text"
                        value={morningMeds}
                        onChange={(e) => setMorningMeds(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-purple-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-indigo-400 block mb-1">Lần dùng 2 / buổi tối nếu đơn ghi rõ:</label>
                      <input
                        type="text"
                        value={eveningMeds}
                        onChange={(e) => setEveningMeds(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-purple-500 focus:outline-none"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {/* Sáng */}
                    <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 flex items-center justify-between gap-2 print:bg-slate-50 print:border-slate-200">
                      <div className="flex items-center gap-2.5">
                        <span className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/20 text-[11px] font-bold print:bg-amber-100 print:text-amber-900">
                          LẦN 1
                        </span>
                        <div className="text-xs font-bold text-slate-100 print:text-slate-900">
                          {morningMeds}
                        </div>
                      </div>
                    </div>

                    {/* Tối */}
                    <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 flex items-center justify-between gap-2 print:bg-slate-50 print:border-slate-200">
                      <div className="flex items-center gap-2.5">
                        <span className="px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 text-[11px] font-bold print:bg-blue-100 print:text-blue-900">
                          LẦN 2
                        </span>
                        <div className="text-xs font-bold text-slate-100 print:text-slate-900">
                          {eveningMeds}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="text-[11px] text-slate-400 print:text-slate-600 italic pt-1 space-y-1">
                  <p>{medicationNote}</p>
                  <p>* Đối chiếu đơn/nhãn thuốc trước khi dùng; không tự bỏ thuốc, đổi liều hoặc uống dồn liều.</p>
                </div>
              </div>

              {/* 2. CHẾ ĐỘ DINH DƯỠNG & KIÊNG CỮ */}
              <div className="care-print-card bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-md print:bg-white print:border print:border-slate-300 print:rounded-lg print:p-3">
                <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wider pb-2 border-b border-slate-800 print:text-slate-900 print:border-slate-300">
                  <Apple className="w-4 h-4 text-emerald-400 print:text-slate-800" />
                  <span>2. Chế Độ Ăn Uống &amp; Kiêng Cữ</span>
                </div>

                {isEditing ? (
                  <div className="space-y-2.5">
                    <div>
                      <label className="text-[11px] font-bold text-emerald-400 block mb-1">✅ Nên ăn &amp; Uống đủ:</label>
                      <textarea
                        value={dietGood}
                        onChange={(e) => setDietGood(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none min-h-[50px] resize-y"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-rose-400 block mb-1">❌ Cần kiêng &amp; Hạn chế:</label>
                      <textarea
                        value={dietBad}
                        onChange={(e) => setDietBad(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-rose-500 focus:outline-none min-h-[50px] resize-y"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2 text-xs">
                    <div className="bg-emerald-950/20 p-2.5 rounded-xl border border-emerald-900/30 print:bg-emerald-50 print:border-emerald-200">
                      <div className="font-bold text-emerald-300 mb-1 print:text-emerald-900 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Nên ăn &amp; Uống đủ:
                      </div>
                      <p className="text-slate-300 text-[11px] leading-relaxed print:text-slate-700">
                        {dietGood}
                      </p>
                    </div>

                    <div className="bg-rose-950/20 p-2.5 rounded-xl border border-rose-900/30 print:bg-rose-50 print:border-rose-200">
                      <div className="font-bold text-rose-300 mb-1 print:text-rose-900 flex items-center gap-1">
                        <AlertOctagon className="w-3.5 h-3.5 text-rose-400" /> Cần kiêng &amp; Hạn chế:
                      </div>
                      <p className="text-slate-300 text-[11px] leading-relaxed print:text-slate-700">
                        {dietBad}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* 3. VẬN ĐỘNG & THEO DÕI */}
              <div className="care-print-card bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-md print:bg-white print:border print:border-slate-300 print:rounded-lg print:p-3">
                <div className="flex items-center gap-2 text-cyan-400 font-bold text-xs uppercase tracking-wider pb-2 border-b border-slate-800 print:text-slate-900 print:border-slate-300">
                  <Footprints className="w-4 h-4 text-cyan-400 print:text-slate-800" />
                  <span>3. Vận Động &amp; Thói Quen Sống</span>
                </div>

                {isEditing ? (
                  <div>
                    <label className="text-[11px] font-bold text-cyan-400 block mb-1">Hướng dẫn tập luyện &amp; thói quen:</label>
                    <textarea
                      value={exercise}
                      onChange={(e) => setExercise(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none min-h-[80px] resize-y"
                    />
                  </div>
                ) : (
                  <div className="space-y-2 text-xs text-slate-300 print:text-slate-800">
                    <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800 print:bg-slate-50 print:border-slate-200">
                      <p className="text-[11px] text-slate-300 leading-relaxed print:text-slate-700">
                        {exercise}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* 4. XỬ TRÍ CẤP CỨU & CẢNH BÁO NGUY HIỂM */}
              <div className="care-print-card bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-md print:bg-white print:border print:border-slate-300 print:rounded-lg print:p-3">
                <div className="flex items-center gap-2 text-rose-400 font-bold text-xs uppercase tracking-wider pb-2 border-b border-slate-800 print:text-slate-900 print:border-slate-300">
                  <AlertOctagon className="w-4 h-4 text-rose-400 print:text-slate-800" />
                  <span>4. Cờ cảnh báo &amp; xử trí cấp cứu</span>
                </div>

                {isEditing ? (
                  <div className="space-y-2">
                    <div>
                      <label className="text-[11px] font-bold text-rose-400 block mb-1">Cách xử trí cấp cứu:</label>
                      <textarea
                        value={warning}
                        onChange={(e) => setWarning(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:border-rose-500 focus:outline-none min-h-[60px] resize-y"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[10px] text-slate-400 block">Kế hoạch tái khám:</label>
                        <input
                          type="text"
                          value={followUp}
                          onChange={(e) => setFollowUp(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-xs text-slate-200"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block">Tên Bác sĩ ký:</label>
                        <input
                          type="text"
                          value={doctorSignName}
                          onChange={(e) => setDoctorSignName(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-xs text-slate-200"
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="bg-rose-950/30 p-2.5 rounded-xl border border-rose-800/40 text-xs space-y-1.5 print:bg-rose-50 print:border-rose-200">
                      <div className="bg-slate-900/90 p-2 rounded-lg text-[11px] text-amber-300 font-medium print:bg-white print:text-slate-900 print:border print:border-slate-300">
                        {warning}
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-300 print:text-slate-800 pt-1">
                      <span className="flex items-center gap-1 font-bold text-teal-300 print:text-slate-900">
                        <PhoneCall className="w-3.5 h-3.5 text-teal-400" /> Hotline: 1900 8888
                      </span>
                      <span className="max-w-[60%] text-right"><strong>{followUp}</strong></span>
                    </div>
                  </div>
                )}
              </div>

            </div>

          </div>

          {/* 4. Modal Footer & Quick QR Info (Screen) / Signatures (Print) */}
          
          {/* Screen Footer */}
          <div className="no-print p-4 sm:px-6 border-t border-white/10 bg-slate-950/90 flex items-center justify-between shrink-0 text-xs text-slate-400 flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border ${requiresReview ? 'bg-slate-900 border-slate-700 text-slate-500' : 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'}`}>
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <span className="font-bold text-slate-200 block">{requiresReview ? 'Chưa phát hành mã QR' : 'Sẵn sàng phát hành bản có mã QR nghe'}</span>
                <span className="text-[11px] text-slate-400">QR thật sẽ được tạo trong PDF từ đúng nội dung bác sĩ đã ký duyệt.</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleExportPdf}
                disabled={isExportingPdf || requiresReview}
                className="px-4 py-2 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white font-bold rounded-xl text-xs transition-all shadow-md shadow-teal-950/40 flex items-center gap-1.5 disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                <span>{isExportingPdf ? 'Đang tạo PDF...' : 'Xuất hướng dẫn PDF'}</span>
              </button>

              <button
                onClick={onClose}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-xl text-xs transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
