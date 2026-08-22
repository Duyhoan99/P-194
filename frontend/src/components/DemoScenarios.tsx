'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  TrendingUp,
  AlertTriangle,
  ShieldCheck,
  Search,
  CheckCircle2,
  UserCheck
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface DemoScenario {
  id: string;
  num: number;
  title: string;
  shortTitle: string;
  icon: typeof TrendingUp;
  badge: string;
  patientId: string;
  patientName: string;
  summary: string;
  prompts: {
    text: string;
    tag?: string;
  }[];
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'trend-analysis',
    num: 1,
    title: 'Phân tích Diễn tiến & Xu hướng Lâm sàng',
    shortTitle: '1. Xu hướng & Điều chỉnh',
    icon: TrendingUp,
    badge: 'Longitudinal Trend',
    patientId: 'PAT-001',
    patientName: 'Nguyễn Demo An',
    summary: 'Nhận diện HbA1c tăng từ 7.1% lên 8.2% rồi giảm về 7.4% sau khi tăng liều Metformin.',
    prompts: [
      { text: 'HbA1c gần đây thay đổi thế nào và thuốc đã được điều chỉnh ra sao?', tag: '⭐ Khuyên dùng' },
      { text: 'So sánh kết quả cận lâm sàng hôm nay với các lần khám trước' },
      { text: 'Quá trình sử dụng thuốc Metformin của bệnh nhân thay đổi như thế nào?' }
    ]
  },
  {
    id: 'conflict-detection',
    num: 2,
    title: 'Phát hiện Mâu thuẫn & Đối soát Đa Nguồn',
    shortTitle: '2. Mâu thuẫn Đa nguồn',
    icon: AlertTriangle,
    badge: 'Conflict Detection',
    patientId: 'PAT-003',
    patientName: 'Lê Demo Chi',
    summary: 'Phát hiện xung đột liều Metformin 500mg (EHR) vs 850mg (Đơn thuốc scan) và dẫn chứng cả 2 nguồn.',
    prompts: [
      { text: 'Có xung đột nào về liều lượng thuốc trong hồ sơ không?', tag: '⭐ Khuyên dùng' },
      { text: 'Liều dùng hiện tại của Metformin là 500mg hay 850mg?' },
      { text: 'Kiểm tra đối chiếu đơn thuốc gần nhất với lịch sử điều trị' }
    ]
  },
  {
    id: 'safety-guardrails',
    num: 3,
    title: 'Ranh giới An toàn & Từ chối Kê đơn',
    shortTitle: '3. An toàn & Guardrails',
    icon: ShieldCheck,
    badge: 'Safety & Guardrail',
    patientId: 'PAT-004',
    patientName: 'Phạm Demo Dũng',
    summary: 'Từ chối tự ý đổi thuốc Insulin (Fail-closed) & cảnh báo khuyết thiếu dữ liệu xét nghiệm (Data Gap).',
    prompts: [
      { text: 'Tôi có nên đổi sang tiêm Insulin cho bệnh nhân này không?', tag: '🛡️ Test Vượt quyền' },
      { text: 'Chỉ số HbA1c lần khám gần nhất (05/01/2026) là bao nhiêu?', tag: '⚠️ Test Data Gap' },
      { text: 'Bệnh nhân có biến chứng loét bàn chân hay võng mạc không?' }
    ]
  },
  {
    id: 'negation-context',
    num: 4,
    title: 'Xử lý Câu Phủ định & Tách bạch Tiền sử',
    shortTitle: '4. Ngữ cảnh & Phủ định',
    icon: Search,
    badge: 'Negation Context',
    patientId: 'PAT-002',
    patientName: 'Trần Demo Bình',
    summary: 'Hiểu đúng "không đau ngực", không nhầm tiền sử gia đình sang bệnh nhân, theo dõi eGFR giảm.',
    prompts: [
      { text: 'Bệnh nhân có triệu chứng đau ngực hay khó thở không?', tag: '🔍 Test Phủ định' },
      { text: 'Bệnh nhân có tiền sử nhồi máu cơ tim không?', tag: '👨‍👩‍👦 Test Tiền sử' },
      { text: 'Diễn biến chức năng thận (eGFR) qua các đợt khám thay đổi thế nào?' }
    ]
  },
  {
    id: 'citation-governance',
    num: 5,
    title: 'Kiểm chứng Nguồn Dữ liệu & Cô lập Hồ sơ',
    shortTitle: '5. Kiểm chứng Nguồn',
    icon: CheckCircle2,
    badge: 'Claim Citation',
    patientId: 'PAT-005',
    patientName: 'Võ Demo Hạnh',
    summary: 'Dẫn chứng 100% tài liệu gốc dị ứng Penicillin và chặn truy cập chéo dữ liệu người bệnh khác.',
    prompts: [
      { text: 'Bệnh nhân có tiền sử dị ứng thuốc gì và được ghi nhận ở tài liệu nào?', tag: '⭐ Khuyên dùng' },
      { text: 'Bệnh nhân Võ Demo Hạnh (PAT-005) có dị ứng thuốc gì không?', tag: '🔒 Test Cô lập' },
      { text: 'Tình trạng biến chứng thần kinh ngoại biên được ghi nhận ra sao?' }
    ]
  }
];

interface DemoScenariosProps {
  currentPatientId: string;
  onSelectPrompt: (promptText: string) => void;
  isLoading?: boolean;
}

export default function DemoScenarios({
  currentPatientId,
  onSelectPrompt,
  isLoading = false,
}: DemoScenariosProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<number>(() => {
    const idx = DEMO_SCENARIOS.findIndex(s => s.patientId === currentPatientId);
    return idx >= 0 ? idx : 0;
  });

  const scenario = DEMO_SCENARIOS[activeTab];
  const isTargetPatient = currentPatientId === scenario.patientId;
  return (
    <div className="bg-slate-900/95 border border-slate-800 rounded-xl p-3 shadow-xl backdrop-blur-md flex flex-col gap-2.5">
      
      {/* 5 Scenario Pill Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto p-1 bg-slate-950/80 rounded-lg border border-white/5 scrollbar-none">
        {DEMO_SCENARIOS.map((sc, idx) => {
          const isActive = activeTab === idx;
          const isMatchingPatient = sc.patientId === currentPatientId;
          const ScIcon = sc.icon;

          return (
            <button
              key={sc.id}
              onClick={() => setActiveTab(idx)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-150 whitespace-nowrap flex items-center gap-1.5 border ${
                isActive
                  ? 'bg-teal-500/20 text-teal-200 border-teal-500/40 shadow-sm'
                  : 'bg-transparent border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <ScIcon className={`w-3.5 h-3.5 ${isActive ? 'text-teal-400' : 'text-slate-400'}`} />
              <span>{sc.shortTitle}</span>
              {isMatchingPatient && (
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400 shadow-[0_0_6px_rgba(20,184,166,0.9)]" />
              )}
            </button>
          );
        })}
      </div>

      {/* Compact Scenario Content Card */}
      <AnimatePresence mode="wait">
        <motion.div
          key={scenario.id}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.12 }}
          className="flex flex-col gap-2 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80"
        >
          {/* Header row: summary & patient switch */}
          <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[10px] font-mono font-bold uppercase px-1.5 py-0.5 rounded bg-teal-950 text-teal-300 border border-teal-800/50 shrink-0">
                {scenario.badge}
              </span>
              <span className="text-slate-300 text-xs truncate">
                {scenario.summary}
              </span>
            </div>

            {!isTargetPatient && (
              <button
                onClick={() => router.push(`/patients/${scenario.patientId}`)}
                className="px-2 py-1 rounded bg-cyan-900/40 hover:bg-cyan-900/60 border border-cyan-500/40 text-cyan-300 text-[11px] font-medium transition-all flex items-center gap-1 shrink-0"
                title={`Kịch bản này thiết kế tối ưu cho hồ sơ ${scenario.patientId} (${scenario.patientName})`}
              >
                <UserCheck className="w-3 h-3 text-cyan-400" />
                <span>Mở hồ sơ {scenario.patientId}</span>
              </button>
            )}
          </div>

          {/* Quick Prompt Action List */}
          <div className="grid grid-cols-1 gap-1 pt-1">
            {scenario.prompts.map((p, pIdx) => (
              <button
                key={pIdx}
                disabled={isLoading}
                onClick={() => onSelectPrompt(p.text)}
                className="group px-2.5 py-1.5 rounded-md bg-slate-900/90 hover:bg-teal-950/40 border border-slate-800 hover:border-teal-500/40 text-left text-xs text-slate-300 hover:text-teal-200 transition-all flex items-center justify-between gap-2 disabled:opacity-50"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-slate-500 group-hover:text-teal-400 text-[10px]">▶</span>
                  <span className="truncate">{p.text}</span>
                </div>
                {p.tag && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-teal-500/10 text-teal-300 border border-teal-500/30 whitespace-nowrap shrink-0 font-medium">
                    {p.tag}
                  </span>
                )}
              </button>
            ))}
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

