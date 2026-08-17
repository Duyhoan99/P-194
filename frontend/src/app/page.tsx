'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Sparkles, ArrowRight, ShieldCheck, Award, 
  BrainCircuit, HeartHandshake, FileText, Activity, 
  UserRound, ChevronLeft, ChevronRight, Moon, Sun,
  Menu, X, Building2, ExternalLink, Clock, FileSignature,
  Microscope, HeartPulse, Stethoscope, CheckCircle2, Lock,
  Check, AlertTriangle, Eye, Database, Cpu, Layers,
  Zap, Search, HelpCircle, ArrowUpRight, Play, RefreshCw,
  AlertCircle, TrendingUp, FileCheck, CheckCircle, Bot
} from 'lucide-react';

export default function LandingPage() {
  const [isDark, setIsDark] = useState(true);
  const [activeSpecialty, setActiveSpecialty] = useState(0);
  const [activeSandboxTab, setActiveSandboxTab] = useState<'ocr' | 'timeline' | 'ask'>('ocr');
  const [selectedOcrFact, setSelectedOcrFact] = useState(0);
  const [activePromptIndex, setActivePromptIndex] = useState(0);

  useEffect(() => {
    const isDarkMode = document.documentElement.classList.contains('dark') || 
      !document.documentElement.classList.contains('light');
    setIsDark(isDarkMode);
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    }
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    if (nextDark) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  };

  // 4 Specialty Profiles
  const specialtyProfiles = [
    {
      id: 0,
      title: 'Đái Tháo Đường Type 2',
      category: 'Nội Tiết',
      icon: HeartPulse,
      metrics: { primary: 'HbA1c: 8.4 %', trend: '+1.0% trong 6 tháng' },
      description: 'Phát hiện sớm đà tăng lại của HbA1c và đánh giá hiệu quả phối hợp thuốc.',
      accent: 'from-cyan-500 to-blue-600'
    },
    {
      id: 1,
      title: 'Tăng Huyết Áp Kháng Trị',
      category: 'Tim Mạch',
      icon: Activity,
      metrics: { primary: 'HA: 158/94 mmHg', trend: 'Cần hạ <130/80' },
      description: 'Rà soát phác đồ Amlodipine + Losartan, cảnh báo nguy cơ tim mạch sớm.',
      accent: 'from-blue-600 to-indigo-600'
    },
    {
      id: 2,
      title: 'Bệnh Thận Mạn (CKD G3a)',
      category: 'Thận Học',
      icon: Microscope,
      metrics: { primary: 'eGFR: 48 mL/min', trend: 'Giảm 22.5% (G3a)' },
      description: 'Cảnh báo chức năng thận suy giảm và khuyến nghị giảm liều Metformin an toàn.',
      accent: 'from-emerald-500 to-teal-600'
    },
    {
      id: 3,
      title: 'Hội Chẩn Chuyển Tuyến',
      category: 'Đa Chuyên Khoa',
      icon: FileSignature,
      metrics: { primary: '100% Dẫn Chứng Gốc', trend: 'Sẵn sàng ký số' },
      description: 'Hợp nhất toàn bộ hồ sơ khám nội ngoại trú thành bản tóm tắt chuyển viện duy nhất.',
      accent: 'from-amber-500 to-orange-600'
    }
  ];

  // OCR Facts for Sandbox
  const ocrFacts = [
    {
      id: 0,
      name: 'HbA1c (Hemoglobin A1c)',
      value: '8.4 %',
      ref: '< 5.7 %',
      status: 'TĂNG CAO',
      statusClass: 'bg-red-500/25 text-red-400 border-red-500/40',
      box: { top: '34%', left: '6%', width: '88%', height: '12%' },
      docNote: 'Bảng Xét Nghiệm Máu (15/01/2026)'
    },
    {
      id: 1,
      name: 'Creatinine Huyết thanh',
      value: '142 µmol/L',
      ref: '62 - 106',
      status: 'BẤT THƯỜNG',
      statusClass: 'bg-amber-500/25 text-amber-400 border-amber-500/40',
      box: { top: '49%', left: '6%', width: '88%', height: '12%' },
      docNote: 'Tăng liên tục từ mốc 118 lên 142 µmol/L'
    },
    {
      id: 2,
      name: 'eGFR (Độ lọc cầu thận)',
      value: '48 mL/min',
      ref: '> 90',
      status: 'CKD G3a',
      statusClass: 'bg-cyan-500/25 text-cyan-300 border-cyan-500/40',
      box: { top: '64%', left: '6%', width: '88%', height: '12%' },
      docNote: 'Cần giảm liều thuốc đào thải qua thận'
    }
  ];

  // Ask the Chart Sample Prompts
  const askPrompts = [
    {
      q: '🔍 Diễn biến eGFR 12 tháng qua?',
      a: 'eGFR giảm từ 62 xuống 48 mL/min/1.73m² (CKD G3a). Khuyến nghị giảm liều Metformin dưới 1000mg/ngày.',
      citations: ['📄 PDF Xét nghiệm 15/01/2026', '🔗 FHIR Observation #obs-892']
    },
    {
      q: '💊 Lịch sử điều chỉnh thuốc huyết áp?',
      a: 'Đợt khám 08/11/2024: Tăng Amlodipine lên 10mg/ngày và thêm Losartan 50mg/ngày do HA 158/92 mmHg.',
      citations: ['📄 PDF Đơn thuốc 08/11/2024', '🔗 FHIR MedicationRequest #med-304']
    },
    {
      q: '⚠️ Tương tác Metformin & SGLT2i?',
      a: 'Phối hợp an toàn nhưng cần bù đủ dịch và theo dõi Creatinine mỗi 3 tháng do eGFR = 48 mL/min.',
      citations: ['📘 ADA/EASD 2024', '🔗 FHIR Condition #cond-t2d-01']
    }
  ];

  const standards = [
    'HL7 FHIR R4', 'ADA Diabetes 2024', 'KDIGO Renal Practice', 
    'ACC/AHA Cardiology', 'ICD-10 Diagnostic', 'SNOMED CT', 
    'LOINC Database', 'HIPAA Privacy', 'Fail-Closed Zero Trust'
  ];

  return (
    <div className={`min-h-screen transition-colors duration-500 font-sans ${isDark ? 'bg-[#02050e] text-slate-100' : 'bg-[#f8fafc] text-slate-900'}`}>
      
      {/* VIBRANT AMBIENT LIGHT MESH */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className={`absolute -top-40 left-1/3 w-[1400px] h-[850px] rounded-full blur-[260px] opacity-45 transition-colors duration-1000 ${isDark ? 'bg-cyan-500' : 'bg-cyan-300'}`} />
        <div className={`absolute top-[400px] -right-40 w-[1200px] h-[1200px] rounded-full blur-[280px] opacity-35 transition-colors duration-1000 ${isDark ? 'bg-blue-600' : 'bg-blue-300'}`} />
        <div className={`absolute bottom-20 -left-20 w-[1200px] h-[800px] rounded-full blur-[280px] opacity-30 transition-colors duration-1000 ${isDark ? 'bg-emerald-500' : 'bg-emerald-300'}`} />
      </div>

      {/* 1. HEADER (WIDESCREEN EXPANDED FLOATING HUD) */}
      <header className="sticky top-0 z-50 w-full px-4 sm:px-10 pt-5 pb-3">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 rounded-3xl liquid-glass-bar px-8 sm:px-10 py-4 shadow-2xl backdrop-blur-2xl border border-cyan-500/30 dark:border-white/15">
          
          {/* Brand Identity */}
          <Link href="/" className="flex items-center gap-4 group">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-cyan-400 via-blue-600 to-indigo-600 text-white shadow-2xl shadow-cyan-500/40 group-hover:scale-105 transition-transform duration-300">
              <Stethoscope className="h-8 w-8" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <span className="font-black text-2xl sm:text-3xl tracking-tight bg-gradient-to-r from-cyan-400 via-blue-400 to-emerald-400 bg-clip-text text-transparent">
                  CLINICAL COPILOT
                </span>
                <span className="text-xs font-black px-3.5 py-1 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 uppercase tracking-widest">
                  P-194
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400 font-bold hidden sm:block">
                AI Rà Soát Bệnh Án Dọc &amp; Minh Bạch Dẫn Chứng
              </p>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="hidden items-center gap-2 rounded-full border border-slate-200/80 dark:border-white/10 bg-white/70 dark:bg-slate-900/80 p-2 backdrop-blur-xl lg:flex shadow-md">
            <Link href="/" className="flex items-center gap-1.5 rounded-full px-6 py-2.5 text-sm font-black bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-md">
              Trang chủ
            </Link>
            <a href="#problem-solution" className="flex items-center gap-1.5 rounded-full px-6 py-2.5 text-sm font-bold text-slate-700 dark:text-slate-300 hover:text-cyan-400 transition">
              Vấn Đề &amp; Giải Pháp
            </a>
            <a href="#sandbox" className="flex items-center gap-1.5 rounded-full px-6 py-2.5 text-sm font-bold text-slate-700 dark:text-slate-300 hover:text-cyan-400 transition">
              <Sparkles className="h-4 w-4 text-cyan-400" />
              Demo Trực Tiếp
            </a>
            <Link href="/patients" className="flex items-center gap-1.5 rounded-full px-6 py-2.5 text-sm font-bold text-slate-700 dark:text-slate-300 hover:text-cyan-400 transition">
              Bệnh Nhân
            </Link>
            <Link href="/case-files" className="flex items-center gap-1.5 rounded-full px-6 py-2.5 text-sm font-bold text-slate-700 dark:text-slate-300 hover:text-cyan-400 transition">
              Hồ Sơ PDF
            </Link>
          </nav>

          {/* Right Action Cluster */}
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Chuyển đổi giao diện Sáng / Tối"
              className="flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-500/30 bg-white/80 dark:bg-slate-800/80 text-slate-700 dark:text-slate-200 hover:scale-105 transition-all shadow-md"
            >
              {isDark ? <Sun className="h-6 w-6 text-amber-300" /> : <Moon className="h-6 w-6 text-slate-700" />}
            </button>

            <Link
              href="/patients"
              className="flex items-center gap-3 px-8 py-3.5 rounded-2xl bg-gradient-to-r from-cyan-400 via-blue-600 to-indigo-600 hover:brightness-110 text-white text-base font-black shadow-2xl shadow-cyan-500/40 transition-all hover:scale-105 active:scale-95"
            >
              <span>Vào Bàn Làm Việc</span>
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>

        </div>
      </header>

      {/* 2. GRAND HERO SECTION (CHỮ GỌN SÚC TÍCH, CỠ CHỮ TO HƠN, 2 NHÂN VẬT PHỦ KÍN KHUNG) */}
      <main className="relative z-10 max-w-[1600px] mx-auto px-4 sm:px-10 pt-10 sm:pt-16 pb-28">
        
        {/* Massive Hero Grid */}
        <div className="grid lg:grid-cols-12 gap-12 xl:gap-16 items-center mb-28">
          
          {/* Left Column: Short, Impactful & Bigger Text (6 cols) */}
          <div className="lg:col-span-6 space-y-9">
            
            {/* Indicator Pill */}
            <div className="inline-flex items-center gap-3.5 px-6 py-3 rounded-full liquid-glass-pill border border-cyan-400/40 text-cyan-300 text-base sm:text-lg font-black shadow-xl">
              <span className="w-4 h-4 rounded-full bg-cyan-400 animate-ping" />
              <span>AI RÀ SOÁT BỆNH ÁN DỌC (FHIR R4 &amp; PDF OCR)</span>
            </div>

            {/* Giant Title */}
            <h1 className="text-5xl sm:text-7xl lg:text-7xl xl:text-8xl font-black tracking-tight leading-[1.05] text-white">
              Chuẩn Mực Rà Soát.{' '}
              <br />
              <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-emerald-400 bg-clip-text text-transparent">
                Minh Bạch 100%
              </span>{' '}
              Bệnh Án Dọc.
            </h1>

            {/* Super Punchy, Bigger Description (Bớt chữ & To hơn) */}
            <p className="text-2xl sm:text-3xl text-slate-100 leading-relaxed font-bold">
              Tự động tóm tắt hồ sơ nhiều năm trong <span className="text-cyan-300 underline decoration-cyan-400 underline-offset-8">3 giây</span>. Phát hiện sớm <span className="text-emerald-400">suy giảm eGFR</span>, <span className="text-amber-400">kháng trị HbA1c</span> và dẫn chứng nguyên văn từng trang PDF gốc.
            </p>

            {/* Big Action Buttons */}
            <div className="flex flex-wrap items-center gap-5 pt-2">
              <Link
                href="/patients"
                className="flex items-center gap-3.5 px-10 py-5 rounded-2xl bg-gradient-to-r from-cyan-400 via-blue-600 to-indigo-600 hover:brightness-110 text-white font-black text-xl shadow-2xl shadow-cyan-500/40 transition-all hover:scale-105 active:scale-95"
              >
                <Activity className="h-7 w-7" />
                <span>Mở Bàn Làm Việc Bác Sĩ</span>
                <ArrowRight className="h-6 w-6" />
              </Link>
              
              <a
                href="#sandbox"
                className="flex items-center gap-3.5 px-9 py-5 rounded-2xl border-2 border-cyan-400/40 bg-slate-900/80 text-xl font-black text-cyan-200 hover:bg-cyan-500/20 shadow-2xl transition-all"
              >
                <Play className="h-6 w-6 text-cyan-400" />
                <span>Thử Demo Trực Tiếp</span>
              </a>
            </div>

            {/* 3 Giant Metric Cards (Chữ to hơn, số to hơn) */}
            <div className="grid grid-cols-3 gap-5 pt-4 max-w-2xl">
              <div className="liquid-glass p-6 rounded-3xl border border-cyan-500/30 text-center shadow-2xl">
                <div className="text-4xl sm:text-5xl font-black text-cyan-400 tracking-tight">100%</div>
                <div className="text-base text-slate-200 font-extrabold mt-2">Dẫn chứng nguồn gốc</div>
              </div>
              <div className="liquid-glass p-6 rounded-3xl border border-emerald-500/30 text-center shadow-2xl">
                <div className="text-4xl sm:text-5xl font-black text-emerald-400 tracking-tight">3 Giây</div>
                <div className="text-base text-slate-200 font-extrabold mt-2">Tóm tắt toàn bộ hồ sơ</div>
              </div>
              <div className="liquid-glass p-6 rounded-3xl border border-indigo-500/30 text-center shadow-2xl">
                <div className="text-4xl sm:text-5xl font-black text-indigo-400 tracking-tight">HITL</div>
                <div className="text-base text-slate-200 font-extrabold mt-2">Bác sĩ ký duyệt</div>
              </div>
            </div>

          </div>

          {/* Right Column: DUAL 3D MASCOTS — TOÀN BỘ KHUNG (PHỦ KÍN 100%, KHÔNG KHOẢNG TRỐNG) (6 cols) */}
          <div className="lg:col-span-6 relative flex items-center justify-center">
            
            {/* Pulsing Light Mesh */}
            <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-tr from-cyan-500/35 via-blue-600/30 to-emerald-500/25 blur-3xl animate-pulse-glow" />

            {/* KHUNG CHỨA DUAL 3D MASCOTS — PHỦ KÍN 100% KHÔNG CHỮ */}
            <div className="relative z-10 w-full rounded-3xl liquid-glass p-3 sm:p-4 border-2 border-cyan-400/40 shadow-2xl animate-float-slow overflow-hidden">
              
              {/* Lưới 2 Cột Chứa 2 Nhân Vật Phủ Kín Toàn Bộ Chiều Cao */}
              <div className="grid grid-cols-2 gap-3 sm:gap-4 w-full rounded-2xl overflow-hidden">
                
                {/* 1. Doctor 3D Mascot (Phủ kín) */}
                <div className="relative w-full aspect-[4/5] rounded-2xl overflow-hidden bg-white flex items-center justify-center shadow-lg">
                  <img 
                    src="/doctor-3d.png" 
                    alt="Bác Sĩ Điều Trị" 
                    className="w-full h-full object-cover scale-115 hover:scale-120 transition-transform duration-500" 
                  />
                </div>

                {/* 2. Robot 3D Mascot (Phủ kín) */}
                <div className="relative w-full aspect-[4/5] rounded-2xl overflow-hidden bg-white flex items-center justify-center shadow-lg">
                  <img 
                    src="/hero-3d.png" 
                    alt="Robot Trợ Lý AI Clinical Copilot" 
                    className="w-full h-full object-cover scale-115 hover:scale-120 transition-transform duration-500" 
                  />
                </div>

              </div>

            </div>

          </div>

        </div>

        {/* 3. VẤN ĐỀ CỐT LÕI & GIẢI PHÁP ĐỘT PHÁ (BỚT CHỮ, TO RÕ RÀNG) */}
        <section id="problem-solution" className="py-14 sm:py-18 scroll-mt-24 mb-24">
          
          <div className="text-center max-w-4xl mx-auto mb-14 space-y-4">
            <div className="inline-flex items-center gap-2.5 rounded-full liquid-glass-pill px-5 py-2 text-sm font-black text-cyan-400 border border-cyan-400/30">
              <AlertCircle className="h-5 w-5" />
              <span>ĐỐI CHIẾU LÂM SÀNG</span>
            </div>
            <h2 className="text-4xl sm:text-6xl font-black text-white tracking-tight">
              Bác Sĩ Đối Mặt Vấn Đề Gì?
            </h2>
            <p className="text-xl sm:text-2xl text-slate-200 font-bold">
              Quy trình đọc thủ công truyền thống vs Trợ lý AI Clinical Copilot:
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-10">
            
            {/* The Old Painful Way (Red Box - Bớt chữ & Chữ to) */}
            <div className="p-10 rounded-3xl liquid-glass border-2 border-red-500/30 space-y-6 shadow-2xl relative overflow-hidden">
              <div className="flex items-center gap-3.5 text-red-400 font-black text-2xl sm:text-3xl">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red-500/20">
                  <AlertTriangle className="h-7 w-7" />
                </div>
                <span>Thủ Công Truyền Thống</span>
              </div>

              <ul className="space-y-6 text-lg sm:text-xl text-slate-200 font-semibold leading-relaxed">
                <li className="flex items-start gap-4">
                  <span className="text-red-400 font-black text-2xl">✕</span>
                  <span><strong>Mất 30-45 phút:</strong> Lật tìm thủ công hàng trăm trang PDF xét nghiệm &amp; đơn thuốc scan.</span>
                </li>
                <li className="flex items-start gap-4">
                  <span className="text-red-400 font-black text-2xl">✕</span>
                  <span><strong>Dễ bỏ sót biến chứng:</strong> Không kịp nhận ra đà suy giảm eGFR từ 78 xuống 48 mL/min.</span>
                </li>
                <li className="flex items-start gap-4">
                  <span className="text-red-400 font-black text-2xl">✕</span>
                  <span><strong>Khó kiểm soát tương tác thuốc:</strong> Rủi ro xung đột phác đồ phối hợp đa năm.</span>
                </li>
              </ul>
            </div>

            {/* The New Clinical Copilot Way (Cyan Box - Bớt chữ & Chữ to) */}
            <div className="p-10 rounded-3xl liquid-glass-strong border-2 border-cyan-400/50 space-y-6 shadow-2xl shadow-cyan-500/10 relative overflow-hidden">
              <div className="flex items-center gap-3.5 text-cyan-300 font-black text-2xl sm:text-3xl">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500/20">
                  <Zap className="h-7 w-7 text-cyan-400" />
                </div>
                <span>Clinical Copilot (P-194)</span>
              </div>

              <ul className="space-y-6 text-lg sm:text-xl text-slate-100 font-semibold leading-relaxed">
                <li className="flex items-start gap-4">
                  <CheckCircle className="h-7 w-7 text-emerald-400 shrink-0 mt-0.5" />
                  <span><strong>Tóm tắt trong 3 giây:</strong> Hợp nhất dữ liệu FHIR R4 &amp; PDF OCR thành dòng thời gian duy nhất.</span>
                </li>
                <li className="flex items-start gap-4">
                  <CheckCircle className="h-7 w-7 text-emerald-400 shrink-0 mt-0.5" />
                  <span><strong>Khoanh vùng Bounding Box 100%:</strong> Định vị tọa độ chính xác từng chỉ số trên bản PDF gốc.</span>
                </li>
                <li className="flex items-start gap-4">
                  <CheckCircle className="h-7 w-7 text-emerald-400 shrink-0 mt-0.5" />
                  <span><strong>Bác sĩ toàn quyền quyết định:</strong> AI tạo bản Draft, Bác sĩ kiểm tra và ký duyệt (HITL).</span>
                </li>
              </ul>
            </div>

          </div>

        </section>

        {/* 4. THE MASTERPIECE: "INTERACTIVE CLINICAL SANDBOX" */}
        <section id="sandbox" className="py-14 sm:py-20 scroll-mt-24 mb-28">
          
          <div className="text-center max-w-4xl mx-auto mb-14 space-y-4">
            <div className="inline-flex items-center gap-2.5 rounded-full liquid-glass-pill px-5 py-2.5 text-sm font-black text-cyan-300 border border-cyan-400/40">
              <Cpu className="h-5 w-5 text-cyan-400" />
              <span>DEMO TƯƠNG TÁC THỰC TẾ</span>
            </div>
            <h2 className="text-4xl sm:text-6xl font-black text-white tracking-tight">
              Thử Nghiệm 3 Công Cụ Lõi
            </h2>
            <p className="text-xl sm:text-2xl text-slate-200 font-bold">
              Bấm chọn giữa các tab bên dưới để trải nghiệm phân tích bệnh án:
            </p>
          </div>

          {/* Sandbox Switcher Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mb-8">
            
            {/* 3 Sandbox Mode Tabs */}
            <div className="flex items-center gap-3 p-2.5 rounded-2xl liquid-glass border-2 border-cyan-400/30 w-full sm:w-auto">
              <button
                onClick={() => setActiveSandboxTab('ocr')}
                className={`flex items-center gap-2.5 px-7 py-3.5 rounded-xl text-base font-black transition-all ${
                  activeSandboxTab === 'ocr' 
                    ? 'bg-gradient-to-r from-cyan-400 to-blue-600 text-white shadow-2xl shadow-cyan-500/40' 
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                <FileText className="h-5 w-5" />
                <span>1. Bounding Box OCR</span>
              </button>

              <button
                onClick={() => setActiveSandboxTab('timeline')}
                className={`flex items-center gap-2.5 px-7 py-3.5 rounded-xl text-base font-black transition-all ${
                  activeSandboxTab === 'timeline' 
                    ? 'bg-gradient-to-r from-cyan-400 to-blue-600 text-white shadow-2xl shadow-cyan-500/40' 
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                <Clock className="h-5 w-5" />
                <span>2. Timeline Dọc</span>
              </button>

              <button
                onClick={() => setActiveSandboxTab('ask')}
                className={`flex items-center gap-2.5 px-7 py-3.5 rounded-xl text-base font-black transition-all ${
                  activeSandboxTab === 'ask' 
                    ? 'bg-gradient-to-r from-cyan-400 to-blue-600 text-white shadow-2xl shadow-cyan-500/40' 
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                <Sparkles className="h-5 w-5" />
                <span>3. Ask the Chart</span>
              </button>
            </div>

            <div className="text-base font-bold text-slate-300">
              Bệnh nhân: <span className="text-cyan-300 font-mono text-lg font-black">Nguyễn Văn T. (#PT-194002)</span>
            </div>

          </div>

          {/* Sandbox Main Stage */}
          <div className="rounded-3xl liquid-glass p-8 sm:p-14 shadow-2xl border-2 border-cyan-400/30">
            
            {/* TAB 1: OCR & Bounding Box */}
            {activeSandboxTab === 'ocr' && (
              <div className="grid lg:grid-cols-12 gap-12 items-start">
                
                {/* Left: Scanned PDF Visualizer (7 cols) */}
                <div className="lg:col-span-7 space-y-5">
                  <div className="flex items-center justify-between text-base font-mono text-slate-400 pb-3 border-b border-slate-700">
                    <span className="font-bold text-cyan-300 flex items-center gap-2.5">
                      <FileText className="h-5 w-5" />
                      PHIEU_XET_NGHIEM_SINH_HOA_2026.PDF
                    </span>
                    <span>Tọa độ Bounding Box</span>
                  </div>

                  <div className="relative aspect-[4/3] bg-slate-950 rounded-3xl p-8 border-2 border-slate-700 font-mono text-base overflow-hidden select-none shadow-2xl text-slate-200">
                    
                    <div className="text-center pb-5 border-b border-slate-800 mb-5">
                      <div className="text-lg text-slate-200 font-black">KHOA XÉT NGHIỆM — BỆNH VIỆN ĐA KHOA</div>
                      <div className="text-sm text-slate-500">PHIẾU XÉT NGHIỆM SINH HÓA MÁU (15/01/2026)</div>
                    </div>

                    <div className="grid grid-cols-12 text-sm text-slate-400 font-bold border-b border-slate-800 pb-3 mb-4">
                      <span className="col-span-6">Thông số</span>
                      <span className="col-span-3 text-right">Kết quả</span>
                      <span className="col-span-3 text-right">Tham chiếu</span>
                    </div>

                    <div className="space-y-4 text-base">
                      {ocrFacts.map((f, idx) => (
                        <div 
                          key={idx}
                          onClick={() => setSelectedOcrFact(idx)}
                          className={`grid grid-cols-12 items-center py-3.5 px-4 rounded-xl cursor-pointer transition-all ${
                            selectedOcrFact === idx 
                              ? 'bg-cyan-500/30 text-white border-2 border-cyan-400 shadow-xl' 
                              : 'text-slate-300 hover:bg-white/5'
                          }`}
                        >
                          <span className="col-span-6 font-bold">{f.name}</span>
                          <span className="col-span-3 text-right font-black text-cyan-300 text-lg">{f.value}</span>
                          <span className="col-span-3 text-right text-slate-400">{f.ref}</span>
                        </div>
                      ))}
                    </div>

                    {/* Bounding Box Visual Pulse */}
                    <div 
                      className="absolute border-3 border-dashed border-cyan-400 bg-cyan-400/20 rounded-xl pointer-events-none transition-all duration-300 animate-pulse-glow"
                      style={{
                        top: ocrFacts[selectedOcrFact].box.top,
                        left: ocrFacts[selectedOcrFact].box.left,
                        width: ocrFacts[selectedOcrFact].box.width,
                        height: ocrFacts[selectedOcrFact].box.height
                      }}
                    >
                      <span className="absolute -top-8 left-0 bg-cyan-400 text-slate-950 font-black px-3 py-1 rounded text-xs shadow-xl">
                        BOUNDING_BOX #{selectedOcrFact + 1}
                      </span>
                    </div>

                  </div>
                </div>

                {/* Right: Fact Inspector & Doctor Action (5 cols) */}
                <div className="lg:col-span-5 space-y-6">
                  
                  <span className="text-base font-black text-cyan-300 uppercase tracking-wider">
                    Nhấp chọn thông số:
                  </span>

                  <div className="space-y-4">
                    {ocrFacts.map((f, idx) => (
                      <div
                        key={idx}
                        onClick={() => setSelectedOcrFact(idx)}
                        className={`p-6 rounded-2xl border-2 transition-all cursor-pointer ${
                          selectedOcrFact === idx 
                            ? 'liquid-glass-strong border-cyan-400 shadow-2xl scale-[1.02]' 
                            : 'bg-slate-900/60 border-slate-800'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-lg font-bold text-white">{f.name}</span>
                          <span className={`text-xs font-black px-3.5 py-1 rounded-full border ${f.statusClass}`}>
                            {f.status}
                          </span>
                        </div>
                        <div className="text-3xl font-black text-cyan-300 mt-2">
                          {f.value}
                        </div>
                        <div className="text-sm text-slate-400 mt-2">
                          {f.docNote}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="p-6 rounded-2xl liquid-glass-strong border-2 border-emerald-500/40 flex items-center justify-between shadow-2xl">
                    <div className="flex items-center gap-3.5">
                      <ShieldCheck className="h-7 w-7 text-emerald-400" />
                      <span className="text-lg font-bold text-white">
                        Bác sĩ xác nhận
                      </span>
                    </div>

                    <button className="px-8 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-base flex items-center gap-2.5 shadow-xl">
                      <Check className="h-5 w-5" />
                      <span>Xác nhận</span>
                    </button>
                  </div>

                </div>

              </div>
            )}

            {/* TAB 2: Longitudinal Timeline */}
            {activeSandboxTab === 'timeline' && (
              <div className="space-y-10">
                <div className="text-xl sm:text-2xl text-slate-200 max-w-4xl font-bold leading-relaxed">
                  Dòng thời gian dọc tổng hợp diễn biến 4 đợt tái khám (2024 - 2026):
                </div>

                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
                  
                  <div className="p-7 rounded-3xl liquid-glass border border-slate-700 space-y-4 shadow-xl">
                    <div className="text-sm font-black text-cyan-400 uppercase tracking-wider">03/2024 · Khám Đầu</div>
                    <div className="text-xl font-bold text-white">ĐTĐ T2 &amp; THA</div>
                    <div className="text-base text-slate-300 space-y-2 pt-4 border-t border-slate-800">
                      <div>• HbA1c: <strong className="text-red-400">9.2 %</strong></div>
                      <div>• eGFR: <strong className="text-cyan-300">78 mL/min</strong></div>
                      <div>• Metformin 500mg x 2</div>
                    </div>
                  </div>

                  <div className="p-7 rounded-3xl liquid-glass border border-slate-700 space-y-4 shadow-xl">
                    <div className="text-sm font-black text-blue-400 uppercase tracking-wider">11/2024 · Tái Khám</div>
                    <div className="text-xl font-bold text-white">Đổi Phác Đồ HA</div>
                    <div className="text-base text-slate-300 space-y-2 pt-4 border-t border-slate-800">
                      <div>• HbA1c: <strong className="text-amber-400">8.1 %</strong></div>
                      <div>• HA: <strong className="text-red-400">158/92 mmHg</strong></div>
                      <div>• Tăng Amlodipine 10mg</div>
                    </div>
                  </div>

                  <div className="p-7 rounded-3xl liquid-glass border border-slate-700 space-y-4 shadow-xl">
                    <div className="text-sm font-black text-teal-400 uppercase tracking-wider">07/2025 · Rà Soát</div>
                    <div className="text-xl font-bold text-white">Phát Hiện CKD G2</div>
                    <div className="text-base text-slate-300 space-y-2 pt-4 border-t border-slate-800">
                      <div>• HbA1c: <strong className="text-emerald-400">7.4 %</strong></div>
                      <div>• eGFR: <strong className="text-amber-400">62 mL/min</strong></div>
                      <div>• Thêm Dapagliflozin 10mg</div>
                    </div>
                  </div>

                  <div className="p-7 rounded-3xl liquid-glass-strong border-2 border-emerald-400/60 space-y-4 shadow-2xl">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-black text-emerald-400 uppercase tracking-wider">01/2026 · Hiện Tại</span>
                      <span className="text-xs font-black px-3 py-1 rounded bg-emerald-500/20 text-emerald-300">MỚI</span>
                    </div>
                    <div className="text-xl font-bold text-white">Cảnh Báo CKD G3a</div>
                    <div className="text-base text-slate-200 space-y-2 pt-4 border-t border-slate-800">
                      <div>• HbA1c: <strong className="text-red-400">8.4 %</strong> (Tăng lại)</div>
                      <div>• eGFR: <strong className="text-red-400">48 mL/min</strong> (G3a)</div>
                      <div>• Giảm liều Metformin</div>
                    </div>
                  </div>

                </div>
              </div>
            )}

            {/* TAB 3: Ask the Chart RAG */}
            {activeSandboxTab === 'ask' && (
              <div className="space-y-10">
                
                <span className="text-lg font-black text-cyan-300 uppercase tracking-wider">
                  Bác sĩ bấm chọn câu hỏi:
                </span>

                <div className="flex flex-wrap gap-3.5">
                  {askPrompts.map((item, idx) => (
                    <button
                      key={idx}
                      onClick={() => setActivePromptIndex(idx)}
                      className={`px-7 py-4 rounded-2xl text-base font-black transition-all text-left border-2 ${
                        activePromptIndex === idx
                          ? 'bg-gradient-to-r from-cyan-400 to-blue-600 text-white border-transparent shadow-2xl shadow-cyan-500/40'
                          : 'liquid-glass text-slate-300 border-slate-800 hover:border-cyan-400/50'
                      }`}
                    >
                      {item.q}
                    </button>
                  ))}
                </div>

                {/* AI Answer with Verified Grounding */}
                <div className="p-10 rounded-3xl liquid-glass-strong border-2 border-cyan-400/40 space-y-6 shadow-2xl">
                  <div className="flex items-center justify-between pb-5 border-b border-slate-700">
                    <div className="flex items-center gap-3 text-lg font-bold text-cyan-300">
                      <Sparkles className="h-6 w-6" />
                      <span>Câu trả lời từ Clinical RAG Agent</span>
                    </div>
                    <span className="text-xs sm:text-sm font-black px-3.5 py-1.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                      Zero Hallucination
                    </span>
                  </div>

                  <p className="text-xl sm:text-2xl text-slate-100 leading-relaxed font-bold">
                    {askPrompts[activePromptIndex].a}
                  </p>

                  <div className="pt-6 border-t border-slate-700 flex flex-wrap items-center justify-between gap-5">
                    <div className="flex flex-wrap items-center gap-3 text-base">
                      <span className="text-slate-400 font-bold">Dẫn chứng:</span>
                      {askPrompts[activePromptIndex].citations.map((cite, cIdx) => (
                        <span key={cIdx} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 font-bold">
                          <ExternalLink className="h-4 w-4" />
                          {cite}
                        </span>
                      ))}
                    </div>

                    <Link
                      href="/patients"
                      className="px-9 py-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:brightness-110 text-white font-black text-lg flex items-center gap-2.5 shadow-2xl"
                    >
                      <FileSignature className="h-6 w-6" />
                      <span>Ký Duyệt Bệnh Án</span>
                    </Link>
                  </div>
                </div>

              </div>
            )}

          </div>

        </section>

        {/* 5. 4 CHUYÊN KHOA BỆNH LÝ MẠN TÍNH TIÊU BIỂU */}
        <section className="py-14 sm:py-20 mb-24">
          <div className="mx-auto max-w-[1600px]">
            
            <div className="text-center max-w-4xl mx-auto mb-14 space-y-4">
              <p className="text-sm font-black uppercase tracking-[0.2em] text-cyan-400">
                KỊCH BẢN THỰC CHIẾN
              </p>
              <h2 className="text-4xl sm:text-6xl font-black text-white tracking-tight">
                4 Kịch Bản Bệnh Lý Mạn Tính
              </h2>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
              {specialtyProfiles.map((item, idx) => {
                const Icon = item.icon;
                return (
                  <div 
                    key={item.id}
                    onClick={() => setActiveSpecialty(idx)}
                    className={`group relative flex flex-col justify-between rounded-3xl liquid-glass p-8 transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl border-2 cursor-pointer ${
                      activeSpecialty === idx 
                        ? 'border-cyan-400 shadow-2xl shadow-cyan-500/20 scale-[1.02]' 
                        : 'border-slate-800'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-6">
                        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-500/15 text-cyan-300 group-hover:scale-110 transition-transform">
                          <Icon className="h-8 w-8" />
                        </div>
                        <span className="text-xs font-black px-3.5 py-1.5 rounded-full bg-slate-800 text-slate-300">
                          {item.category}
                        </span>
                      </div>

                      <h3 className="font-black text-2xl text-white mb-3">
                        {item.title}
                      </h3>

                      <p className="text-base text-slate-300 leading-relaxed mb-6 font-medium">
                        {item.description}
                      </p>
                    </div>

                    <div className="pt-5 border-t border-slate-800 flex items-center justify-between text-base font-black text-cyan-300">
                      <span>{item.metrics.primary}</span>
                      <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </div>
                );
              })}
            </div>

          </div>
        </section>

        {/* 6. TIÊU CHUẨN AN TOÀN Y TẾ & MARQUEE */}
        <section className="w-full overflow-hidden py-12 border-t border-slate-800">
          <div className="max-w-[1600px] mx-auto px-4 mb-8 text-center">
            <p className="text-sm font-black uppercase tracking-[0.2em] text-slate-400">
              TIÊU CHUẨN Y KHOA &amp; PHÁC ĐỒ ĐIỀU TRỊ QUỐC TẾ
            </p>
          </div>

          <div className="relative w-full overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
            <div className="animate-marquee-infinite flex items-center gap-12 py-4">
              {[...standards, ...standards].map((standard, idx) => (
                <div key={idx} className="flex shrink-0 items-center justify-center px-8">
                  <span className="text-lg font-black text-slate-300 hover:text-cyan-300 transition-colors whitespace-nowrap">
                    {standard}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

      </main>

      {/* 7. FOOTER */}
      <footer className="w-full relative border-t border-slate-800 bg-slate-950/80 backdrop-blur-2xl py-12 text-slate-400">
        <div className="mx-auto max-w-[1600px] px-4 sm:px-10 space-y-8">
          
          <div className="flex flex-col md:flex-row items-center justify-between gap-8 pb-8 border-b border-slate-800">
            <div className="flex flex-col sm:flex-row items-center gap-4 text-center sm:text-left">
              <span className="font-black text-2xl tracking-tight text-cyan-400">
                CLINICAL COPILOT
              </span>
              <span className="hidden sm:inline text-slate-700 text-lg">•</span>
              <span className="text-base text-slate-300 font-bold">
                Nền tảng AI Hỗ Trợ Rà Soát Bệnh Án Dọc (P-194 · Cohort 3)
              </span>
            </div>

            <nav className="flex flex-wrap items-center justify-center gap-8 text-base font-bold">
              <Link href="/" className="hover:text-cyan-300 transition">Trang chủ</Link>
              <Link href="/patients" className="hover:text-cyan-300 transition">Danh sách Bệnh nhân</Link>
              <Link href="/case-files" className="hover:text-cyan-300 transition">Tài liệu PDF &amp; OCR</Link>
              <Link href="/help" className="hover:text-cyan-300 transition">Hướng dẫn Bác sĩ</Link>
            </nav>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-slate-500">
            <p className="text-center sm:text-left">
              Bản quyền © 2026 thuộc về Dự án P-194 · AI20K Build Phase Cohort 3
            </p>
            <div className="flex items-center gap-3">
              <span>Chuẩn FHIR R4 &amp; HITL Clinical Governance</span>
            </div>
          </div>

        </div>
      </footer>

    </div>
  );
}
