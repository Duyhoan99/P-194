'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Sparkles, ArrowRight, Award,
  FileText, Activity,
  Moon, Sun, Clock, FileSignature,
  Microscope, HeartPulse, Stethoscope, CheckCircle2,
  AlertTriangle, Database, Cpu,
  Play, TrendingUp, Bot
} from 'lucide-react';

export default function LandingPage() {
  const [isDark, setIsDark] = useState(true);
  const [activeSpecialty, setActiveSpecialty] = useState(0);
  const [activeSandboxTab, setActiveSandboxTab] = useState<'ocr' | 'timeline' | 'ask'>('ocr');
  const [selectedOcrFact, setSelectedOcrFact] = useState(0);
  const [activePromptIndex, setActivePromptIndex] = useState(0);
  const [timelineYear, setTimelineYear] = useState<2024 | 2025 | 2026>(2026);

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
      category: 'Nội Tiết Học',
      icon: HeartPulse,
      metrics: { primary: 'HbA1c: 8.4 %', trend: '+1.0% trong 6 tháng' },
      description: 'Phát hiện sớm đà tăng lại của HbA1c và đánh giá hiệu quả phối hợp phác đồ Metformin + SGLT2i.',
      badge: 'ADA/EASD 2024 Guideline',
      accent: 'from-teal-400 to-cyan-500'
    },
    {
      id: 1,
      title: 'Tăng Huyết Áp Kháng Trị',
      category: 'Tim Mạch Học',
      icon: Activity,
      metrics: { primary: 'Huyết áp: 158/94 mmHg', trend: 'Mục tiêu <130/80' },
      description: 'Rà soát tương tác Amlodipine + Losartan, cảnh báo nguy cơ tim mạch sớm và quá tải thể tích.',
      badge: 'ACC/AHA Clinical Standard',
      accent: 'from-cyan-400 to-blue-500'
    },
    {
      id: 2,
      title: 'Bệnh Thận Mạn (CKD G3a)',
      category: 'Thận Học',
      icon: Microscope,
      metrics: { primary: 'eGFR: 48 mL/min', trend: 'Giảm 22.5% (G3a)' },
      description: 'Phát hiện suy giảm chức năng thận mạn tính và cảnh báo giảm liều thuốc đào thải qua thận.',
      badge: 'KDIGO 2024 Renal Criteria',
      accent: 'from-emerald-400 to-teal-500'
    },
    {
      id: 3,
      title: 'Hội Chẩn Chuyển Tuyến',
      category: 'Đa Chuyên Khoa',
      icon: FileSignature,
      metrics: { primary: '100% Dẫn Chứng Gốc', trend: 'Sẵn sàng ký số' },
      description: 'Hợp nhất toàn bộ hồ sơ khám nội ngoại trú nhiều bệnh viện thành bản tóm tắt chuyển viện duy nhất.',
      badge: 'HL7 FHIR R4 Standard',
      accent: 'from-sky-400 to-indigo-500'
    }
  ];

  // OCR Facts for Sandbox (Tọa độ Bounding Box Khít Khao 100%)
  const ocrFacts = [
    {
      id: 0,
      name: 'HbA1c (Hemoglobin A1c)',
      value: '8.4 %',
      ref: '< 5.7 %',
      status: 'VƯỢT NGƯỠNG',
      statusClass: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
      coords: '[X: 42, Y: 154, W: 520, H: 48]',
      docNote: 'Bảng Xét Nghiệm Máu Tĩnh Mạch (15/01/2026)'
    },
    {
      id: 1,
      name: 'Glucose Máu Lúc Đói (FPG)',
      value: '9.2 mmol/L',
      ref: '3.9 - 6.4',
      status: 'TĂNG CAO',
      statusClass: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
      coords: '[X: 42, Y: 212, W: 520, H: 48]',
      docNote: 'Đường huyết tương lúc đói tăng liên tục qua 3 đợt khám'
    },
    {
      id: 2,
      name: 'Creatinine Huyết Thanh',
      value: '142 µmol/L',
      ref: '62 - 106',
      status: 'TĂNG CAO',
      statusClass: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
      coords: '[X: 42, Y: 270, W: 520, H: 48]',
      docNote: 'Tăng liên tục từ mốc 118 lên 142 µmol/L qua 2 đợt khám'
    },
    {
      id: 3,
      name: 'eGFR (Độ Lọc Cầu Thận)',
      value: '48 mL/min/1.73m²',
      ref: '> 90',
      status: 'CKD G3a',
      statusClass: 'text-cyan-300 bg-cyan-500/10 border-cyan-500/30',
      coords: '[X: 42, Y: 328, W: 520, H: 48]',
      docNote: 'Chỉ định giảm liều thuốc đào thải qua thận (Metformin)'
    }
  ];

  // Sample Prompts for Interactive AI Laboratory
  const askPrompts = [
    {
      q: '🔍 Diễn biến eGFR và chức năng thận 12 tháng qua?',
      a: 'Độ lọc cầu thận eGFR giảm từ 62 xuống 48 mL/min/1.73m² (chuyển sang giai đoạn CKD G3a). Khuyến nghị lâm sàng: Điều chỉnh giảm liều Metformin tối đa 1000mg/ngày và bổ sung bù dịch.',
      citations: ['📄 PDF Xét nghiệm 15/01/2026', '🔗 FHIR Observation #obs-892', '📘 Hướng dẫn KDIGO 2024']
    },
    {
      q: '💊 Quá trình điều chỉnh liều thuốc huyết áp thế nào?',
      a: 'Ngày 08/11/2024: Tăng liều Amlodipine lên 10mg/ngày kết hợp Losartan 50mg/ngày do chỉ số HA tại phòng khám đạt 158/92 mmHg. Đợt tái khám gần nhất ghi nhận HA duy trì 138/84 mmHg.',
      citations: ['📄 PDF Đơn thuốc 08/11/2024', '🔗 FHIR MedicationRequest #med-304']
    },
    {
      q: '⚠️ Có xung đột tương tác thuốc hoặc chống chỉ định nào?',
      a: 'Không ghi nhận tương tác đối kháng nghiêm trọng. Tuy nhiên, việc phối hợp Metformin khi eGFR = 48 mL/min cần giám sát nồng độ Acid Lactic và xét nghiệm Creatinine định kỳ mỗi 3 tháng.',
      citations: ['📘 ADA Diabetes Care 2024', '🔗 FHIR Condition #cond-t2d-01']
    }
  ];

  const standards = [
    { name: 'HL7 FHIR R4', desc: 'Chuẩn trao đổi dữ liệu y tế toàn cầu' },
    { name: 'ADA Diabetes 2024', desc: 'Phác đồ điều trị đái tháo đường quốc tế' },
    { name: 'KDIGO Renal', desc: 'Tiêu chuẩn phân độ bệnh thận mạn' },
    { name: 'ACC/AHA Heart', desc: 'Hướng dẫn quản lý tăng huyết áp' },
    { name: 'SNOMED CT & LOINC', desc: 'Mã hóa lâm sàng & danh mục xét nghiệm' },
    { name: 'Fail-Closed Guardrail', desc: 'Cơ chế triệt tiêu 100% ảo giác y khoa' }
  ];

  return (
    <div className={`min-h-screen transition-colors duration-500 font-sans ${isDark ? 'bg-[#06090e] text-slate-100' : 'bg-[#fbfbfa] text-slate-900'}`}>

      {/* AMBIENT LIGHT MESH — OURA RING MINIMALIST SUBTLE GLOW */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className={`absolute -top-40 left-1/4 w-[1400px] h-[850px] rounded-full blur-[280px] transition-colors duration-1000 ${isDark ? 'bg-teal-500/12' : 'bg-teal-200/30'}`} />
        <div className={`absolute top-[35%] -right-20 w-[1100px] h-[1100px] rounded-full blur-[300px] transition-colors duration-1000 ${isDark ? 'bg-cyan-600/12' : 'bg-cyan-200/25'}`} />
        <div className={`absolute bottom-10 left-10 w-[1000px] h-[800px] rounded-full blur-[280px] transition-colors duration-1000 ${isDark ? 'bg-emerald-500/10' : 'bg-emerald-200/20'}`} />
      </div>

      {/* 1. FLOATING PILL NAVIGATION (1600px Max Width) */}
      <header className="sticky top-0 z-50 w-full px-4 sm:px-10 pt-5 pb-3">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-6 rounded-full px-8 py-4 shadow-2xl oura-glass border border-white/10 backdrop-blur-2xl">

          {/* Brand Identity */}
          <Link href="/" className="flex items-center gap-4 group">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-300 shadow-[0_0_20px_rgba(20,184,166,0.25)] group-hover:scale-105 transition-transform duration-300">
              <Stethoscope className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="font-bold text-xl tracking-tight text-slate-100">
                  Clinical Copilot
                </span>
              </div>
              <p className="text-xs text-slate-400 font-normal hidden sm:block">
                Longitudinal Intelligence &amp; Evidence Grounding
              </p>
            </div>
          </Link>

          {/* Navigation Items with Oura Underline */}
          <nav className="hidden items-center gap-3 lg:flex text-[15px] tracking-wide font-normal text-slate-300">
            <Link href="/" className="px-5 py-2 oura-underline-hover text-teal-300 font-medium">
              Trang chủ
            </Link>
            <a href="#pipeline" className="px-5 py-2 oura-underline-hover hover:text-white transition-colors">
              Kiến trúc Fusion
            </a>
            <a href="#specialties" className="px-5 py-2 oura-underline-hover hover:text-white transition-colors">
              Chuyên khoa
            </a>
            <a href="#sandbox" className="px-5 py-2 oura-underline-hover hover:text-white transition-colors flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-teal-400" />
              Phòng Lab AI
            </a>
            <Link href="/patients" className="px-5 py-2 oura-underline-hover hover:text-white transition-colors">
              Hồ sơ Bệnh nhân
            </Link>
            <Link href="/case-files" className="px-5 py-2 oura-underline-hover hover:text-white transition-colors">
              Tài liệu OCR
            </Link>
          </nav>

          {/* Right Action Cluster */}
          <div className="flex items-center gap-3.5">
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Chuyển đổi giao diện Sáng / Tối"
              className="flex h-11 w-11 items-center justify-center oura-pill text-slate-300 hover:text-white transition-all"
            >
              {isDark ? <Sun className="h-4 w-4 text-amber-300" /> : <Moon className="h-4 w-4 text-slate-700" />}
            </button>

            <Link
              href="/patients"
              className="flex items-center gap-2.5 px-7 py-3 rounded-full oura-pill bg-teal-500/15 border-teal-500/40 text-teal-200 hover:bg-teal-500/25 hover:text-white text-xs font-semibold tracking-wider uppercase transition-all shadow-sm"
            >
              <span>Vào Bàn Làm Việc</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

        </div>
      </header>

      {/* 2. CINEMATIC HERO SECTION (1600px Max Width) */}
      <main className="relative z-10 max-w-[1600px] mx-auto px-4 sm:px-10 pt-10 sm:pt-16 pb-28">

        {/* Grand Grid */}
        <div className="grid lg:grid-cols-12 gap-12 xl:gap-16 items-center mb-28">

          {/* Left Column: Editorial Headline & High-Trust Narrative */}
          <div className="lg:col-span-6 space-y-8">

            {/* Oura Pill Eyebrow */}
            <div className="inline-flex items-center gap-2.5 px-4 py-1.5 oura-pill text-xs font-medium text-teal-300 uppercase tracking-widest">
              <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
              <span>Khoa học lâm sàng · Kiểm định đa nguồn</span>
            </div>

            {/* Main Headline — In đậm mạnh mẽ, trọn vẹn 2 dòng */}
            <h1 className="text-4xl sm:text-6xl lg:text-[52px] xl:text-[60px] font-bold tracking-tight leading-[1.18] text-slate-100">
              Grounded in Science.{' '}
              <span className="block mt-2 font-bold text-transparent bg-clip-text bg-gradient-to-r from-teal-200 via-cyan-200 to-sky-300">
                Rà Soát Bệnh Án Dọc Đa Nguồn.
              </span>
            </h1>

            {/* Description (Chữ to hơn, rõ ràng) */}
            <p className="text-lg sm:text-xl text-slate-200 leading-relaxed font-normal">
              Hợp nhất dữ liệu xét nghiệm, đơn thuốc và bệnh án scan qua nhiều năm thành một bức tranh lâm sàng liên tục. Tự động đối chiếu 100% dẫn chứng nguyên văn với tọa độ Bounding Box từng trang PDF gốc.
            </p>

            {/* CTA Action Buttons */}
            <div className="flex flex-wrap items-center gap-4 pt-2">
              <Link
                href="/patients"
                className="flex items-center gap-3 px-8 py-4 rounded-full oura-pill bg-teal-500/20 border-teal-500/40 hover:border-teal-300 text-teal-100 hover:text-white font-semibold text-sm tracking-wider uppercase shadow-xl shadow-teal-950/40 transition-all hover:scale-[1.02] active:scale-95"
              >
                <Activity className="h-5 w-5 text-teal-400" />
                <span>Mở Bàn Làm Việc Bác Sĩ</span>
                <ArrowRight className="h-4 w-4" />
              </Link>

              <a
                href="#sandbox"
                className="flex items-center gap-2.5 px-8 py-4 rounded-full oura-pill text-sm font-semibold tracking-wider uppercase text-slate-300 hover:text-white transition-all hover:scale-[1.02]"
              >
                <Play className="h-4 w-4 text-cyan-400" />
                <span>Thực Nghiệm AI Sandbox</span>
              </a>
            </div>

            {/* OURA RING SCIENCE & RESEARCH BENTO STATS (Đều tăm tắp 1 hàng ngang) */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 pt-8 border-t border-white/10">
              <div className="flex flex-col">
                <span className="font-serif text-5xl sm:text-7xl font-light text-slate-100 tracking-tight whitespace-nowrap">100%</span>
                <span className="text-sm font-semibold uppercase tracking-wider text-teal-400 mt-2">Dẫn chứng gốc</span>
                <p className="text-xs sm:text-sm text-slate-400 font-normal mt-1 leading-snug">Tọa độ Bounding Box</p>
              </div>

              <div className="flex flex-col">
                <div className="font-serif text-5xl sm:text-7xl font-light text-slate-100 tracking-tight flex items-baseline gap-2 whitespace-nowrap">
                  <span>3</span>
                  <span className="text-3xl sm:text-4xl font-serif font-light text-slate-300">Giây</span>
                </div>
                <span className="text-sm font-semibold uppercase tracking-wider text-cyan-400 mt-2">Tốc độ xử lý</span>
                <p className="text-xs sm:text-sm text-slate-400 font-normal mt-1 leading-snug">Hợp nhất 4 năm hồ sơ</p>
              </div>

              <div className="flex flex-col">
                <span className="font-serif text-5xl sm:text-7xl font-light text-slate-100 tracking-tight whitespace-nowrap">0%</span>
                <span className="text-sm font-semibold uppercase tracking-wider text-emerald-400 mt-2">Ảo giác</span>
                <p className="text-xs sm:text-sm text-slate-400 font-normal mt-1 leading-snug">Fail-Closed Zero Trust</p>
              </div>

              <div className="flex flex-col">
                <span className="font-serif text-5xl sm:text-7xl font-light text-slate-100 tracking-tight whitespace-nowrap">10+</span>
                <span className="text-sm font-semibold uppercase tracking-wider text-sky-400 mt-2">Chuẩn y khoa</span>
                <p className="text-xs sm:text-sm text-slate-400 font-normal mt-1 leading-snug">FHIR, ADA, KDIGO</p>
              </div>
            </div>

          </div>

          {/* Right Column: 3D HOLOGRAPHIC AI WORKSTATION SHOWCASE */}
          <div className="lg:col-span-6 relative">

            {/* Subtle ambient aura */}
            <div className="absolute -inset-2 rounded-3xl bg-gradient-to-tr from-teal-500/25 via-cyan-500/15 to-transparent blur-3xl pointer-events-none" />

            {/* 3D Visual Showcase Container */}
            <div className="relative z-10 oura-glass rounded-3xl p-4 sm:p-5 border border-white/15 shadow-2xl overflow-hidden space-y-4">

              {/* 3D Hologram Master Image (Clean, No Overlay Bar) */}
              <div className="relative w-full aspect-[16/10] rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-black/60 group">
                <img
                  src="/clinical-ai-hologram.jpg"
                  alt="3D Holographic Clinical AI Workstation"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                />

                {/* Floating Telemetry Badges Overlay */}
                <div className="absolute top-3 left-3 flex items-center gap-2 px-3.5 py-1.5 rounded-full oura-glass border border-white/20 text-xs font-mono text-teal-300 shadow-lg">
                  <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
                  <span>3D CLINICAL RADAR</span>
                </div>
              </div>

              {/* 3D Mascot Cards Row (To lớn nổi bật, không có chữ P-194) */}
              <div className="grid grid-cols-2 gap-4 pt-1">
                <div className="p-5 sm:p-6 rounded-2xl oura-glass-card border border-white/10 flex items-center gap-5 hover:border-teal-500/40 transition-all">
                  <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl overflow-hidden bg-white/10 shrink-0 border border-white/15 shadow-lg flex items-center justify-center">
                    <img src="/doctor-3d.png" alt="Bác sĩ" className="w-full h-full object-cover scale-110" />
                  </div>
                  <div>
                    <h4 className="text-base sm:text-lg font-semibold text-slate-100">Bác Sĩ Trưởng Khoa</h4>
                    <p className="text-xs sm:text-sm text-slate-400 mt-1">Kiểm tra &amp; Ký duyệt (HITL)</p>
                  </div>
                </div>

                <div className="p-5 sm:p-6 rounded-2xl oura-glass-card border border-white/10 flex items-center gap-5 hover:border-teal-500/40 transition-all">
                  <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl overflow-hidden bg-white/10 shrink-0 border border-white/15 shadow-lg flex items-center justify-center">
                    <img src="/hero-3d.png" alt="Robot AI" className="w-full h-full object-cover scale-110" />
                  </div>
                  <div>
                    <h4 className="text-base sm:text-lg font-semibold text-slate-100">AI Co-pilot</h4>
                    <p className="text-xs sm:text-sm text-teal-400 font-medium mt-1">Rà soát đa nguồn 3 giây</p>
                  </div>
                </div>
              </div>

            </div>

          </div>

        </div>

        {/* 3. MULTI-SOURCE INGESTION FUSION ARCHITECTURE (WITH 3D OCR SCANNER) */}
        <section id="pipeline" className="py-16 sm:py-24 scroll-mt-20 mb-24 border-t border-white/10">

          <div className="text-center max-w-5xl mx-auto mb-16 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full oura-pill px-4 py-1.5 text-xs font-medium text-teal-300 tracking-widest uppercase">
              <Database className="h-4 w-4" />
              <span>Đa nguồn dữ liệu · FHIR R4 &amp; PDF OCR</span>
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-100 tracking-tight">
              Kiến Trúc Hợp Nhất Đa Chiều
            </h2>
            <p className="text-base sm:text-lg text-slate-300 font-normal max-w-2xl mx-auto">
              Giải quyết triệt để bài toán phân mảnh giữa bệnh án điện tử và tài liệu scan:
            </p>
          </div>

          <div className="grid lg:grid-cols-12 gap-8 items-center">

            {/* 3D OCR Scanner Visual (5 cols) */}
            <div className="lg:col-span-5 rounded-3xl oura-glass p-4 border border-white/10 overflow-hidden shadow-2xl">
              <div className="relative w-full aspect-[4/3] rounded-2xl overflow-hidden border border-white/10">
                <img
                  src="/ocr-bounding-box-3d.jpg"
                  alt="3D Holographic OCR Document Scanner"
                  className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                />
                <div className="absolute top-3 left-3 px-3 py-1 rounded-full oura-glass text-xs font-mono text-teal-300 border border-teal-500/30">
                  LASER BOUNDING BOX ENGINE
                </div>
              </div>
            </div>

            {/* Ingestion Stream Cards (7 cols) */}
            <div className="lg:col-span-7 grid sm:grid-cols-3 gap-5">

              {/* Stream 1 */}
              <div className="p-7 rounded-2xl oura-glass-card space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-300">
                  <Database className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-slate-100">1. Chuẩn Hóa FHIR</h3>
                <p className="text-sm text-slate-300 leading-relaxed">
                  Đồng bộ tự động Encounter, Observation, Medication và Condition theo chuẩn quốc tế.
                </p>
                <span className="inline-block text-xs font-mono text-cyan-300 bg-cyan-500/10 px-2.5 py-1 rounded-full border border-cyan-500/20">
                  HL7 R4 Standard
                </span>
              </div>

              {/* Stream 2 */}
              <div className="p-7 rounded-2xl oura-glass-card space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-300">
                  <FileText className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-slate-100">2. Bounding Box OCR</h3>
                <p className="text-sm text-slate-300 leading-relaxed">
                  Quét từng trang PDF xét nghiệm, trích xuất tọa độ BBox chính xác để bác sĩ đối soát.
                </p>
                <span className="inline-block text-xs font-mono text-teal-300 bg-teal-500/10 px-2.5 py-1 rounded-full border border-teal-500/20">
                  Coordinate Grounded
                </span>
              </div>

              {/* Stream 3 */}
              <div className="p-7 rounded-2xl oura-glass-card space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-300">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-slate-100">3. Ký Duyệt HITL</h3>
                <p className="text-sm text-slate-300 leading-relaxed">
                  AI tạo bản tóm tắt nháp, Bác sĩ giữ toàn quyền kiểm tra, sửa đổi và ký duyệt.
                </p>
                <span className="inline-block text-xs font-mono text-emerald-300 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                  Doctor Approved
                </span>
              </div>

            </div>

          </div>

        </section>

        {/* 4. CLINICAL SPECIALTIES SPECTRUM */}
        <section id="specialties" className="py-16 sm:py-24 scroll-mt-20 mb-24">

          <div className="text-center max-w-5xl mx-auto mb-16 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full oura-pill px-4 py-1.5 text-xs font-medium text-teal-300 tracking-widest uppercase">
              <Microscope className="h-4 w-4" />
              <span>Ứng dụng chuyên khoa đa ngành</span>
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-100 tracking-tight">
              Phù Hợp Mọi Bệnh Cảnh Mạn Tính
            </h2>
            <p className="text-base sm:text-lg text-slate-300 font-normal max-w-2xl mx-auto">
              Được tinh chỉnh theo tiêu chuẩn phác đồ của từng phân ngành y khoa:
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {specialtyProfiles.map((spec, idx) => {
              const Icon = spec.icon;
              return (
                <div
                  key={spec.id}
                  onClick={() => setActiveSpecialty(idx)}
                  className={`p-7 rounded-2xl oura-glass-card cursor-pointer transition-all duration-300 ${activeSpecialty === idx
                      ? 'border-teal-500/50 bg-teal-950/20 shadow-xl shadow-teal-950/30 scale-[1.02]'
                      : 'hover:border-white/20'
                    }`}
                >
                  <div className="flex items-center justify-between mb-5">
                    <div className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-teal-300 shadow-sm">
                      <Icon className="w-7 h-7" />
                    </div>
                    <span className="text-xs font-mono text-slate-300 px-3 py-1 rounded-full oura-pill">
                      {spec.category}
                    </span>
                  </div>

                  <h3 className="text-xl font-semibold text-slate-100 mb-2">{spec.title}</h3>
                  <p className="text-sm text-slate-300 mb-5 leading-relaxed">{spec.description}</p>

                  <div className="pt-4 border-t border-white/5 space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Trọng tâm:</span>
                      <span className="font-mono font-semibold text-teal-300">{spec.metrics.primary}</span>
                    </div>
                    <div className="text-xs sm:text-sm text-teal-400 font-mono flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4" />
                      {spec.metrics.trend}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

        </section>

        {/* 5. INTERACTIVE CLINICAL SANDBOX (LIVE LABORATORY) */}
        <section id="sandbox" className="py-16 sm:py-24 scroll-mt-20 mb-24 border-t border-white/10">

          <div className="text-center max-w-5xl mx-auto mb-12 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full oura-pill px-4 py-1.5 text-xs font-medium text-cyan-300 tracking-widest uppercase">
              <Cpu className="h-4 w-4" />
              <span>Phòng thực nghiệm AI trực tiếp</span>
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-100 tracking-tight">
              Trải Nghiệm 3 Tính Năng Cốt Lõi
            </h2>
            <p className="text-base sm:text-lg text-slate-300 font-normal max-w-2xl mx-auto">
              Bấm chọn giữa các chế độ thực nghiệm bên dưới để tương tác trực tiếp với dữ liệu mẫu:
            </p>
          </div>

          {/* Sandbox Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mb-8">
            <div className="flex items-center gap-2 p-1.5 rounded-full oura-glass w-full sm:w-auto">
              <button
                onClick={() => setActiveSandboxTab('ocr')}
                className={`flex items-center gap-2 px-7 py-3 rounded-full text-xs font-semibold tracking-wide transition-all ${activeSandboxTab === 'ocr'
                    ? 'bg-teal-500/20 border border-teal-500/40 text-teal-200 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                  }`}
              >
                <FileText className="h-4 w-4" />
                <span>1. Bounding Box OCR</span>
              </button>

              <button
                onClick={() => setActiveSandboxTab('timeline')}
                className={`flex items-center gap-2 px-7 py-3 rounded-full text-xs font-semibold tracking-wide transition-all ${activeSandboxTab === 'timeline'
                    ? 'bg-teal-500/20 border border-teal-500/40 text-teal-200 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                  }`}
              >
                <Clock className="h-4 w-4" />
                <span>2. Timeline Dọc 3 Năm</span>
              </button>

              <button
                onClick={() => setActiveSandboxTab('ask')}
                className={`flex items-center gap-2 px-7 py-3 rounded-full text-xs font-semibold tracking-wide transition-all ${activeSandboxTab === 'ask'
                    ? 'bg-teal-500/20 border border-teal-500/40 text-teal-200 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                  }`}
              >
                <Sparkles className="h-4 w-4" />
                <span>3. Ask the Chart AI</span>
              </button>
            </div>

            <div className="text-sm text-slate-400 font-normal">
              Bệnh nhân thử nghiệm: <span className="font-mono text-teal-300 font-semibold">Nguyễn Văn T. (#PT-194002)</span>
            </div>
          </div>

          {/* Sandbox Main Stage */}
          <div className="rounded-3xl oura-glass p-8 sm:p-12 shadow-2xl border border-white/10">

            {/* TAB 1: OCR BOUNDING BOX */}
            {activeSandboxTab === 'ocr' && (
              <div className="grid lg:grid-cols-12 gap-10 items-start">

                {/* Left: Interactive PDF Canvas */}
                <div className="lg:col-span-7 space-y-4">
                  <div className="flex items-center justify-between text-xs font-mono text-slate-400 pb-2 border-b border-white/5">
                    <span className="text-teal-300 flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      PHIEU_XET_NGHIEM_SINH_HOA_2026.PDF
                    </span>
                    <span>Tọa độ Bounding Box Thực Tế</span>
                  </div>

                  <div className="relative bg-[#05080e] rounded-2xl p-6 sm:p-8 border border-white/10 font-mono text-xs overflow-hidden select-none shadow-2xl text-slate-200">
                    
                    {/* Header of Medical Document */}
                    <div className="flex items-center justify-between pb-4 border-b border-white/10 mb-5">
                      <div>
                        <div className="font-bold text-sm sm:text-base text-slate-100 uppercase tracking-wide">
                          Bệnh Viện Đại Học Y Dược — Khoa Sinh Hóa
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          Số phiếu: <span className="text-teal-300">XN-2026-0892</span> · Ngày lấy mẫu: 15/01/2026
                        </div>
                      </div>
                      <div className="px-3 py-1 rounded bg-white/5 border border-white/10 text-[10px] text-slate-400 font-mono">
                        TRANG 1/1 (PDF SCAN)
                      </div>
                    </div>

                    {/* Table Header */}
                    <div className="flex justify-between text-xs text-slate-400 border-b border-white/5 pb-2 mb-3 px-2 uppercase font-semibold">
                      <span>CHỈ SỐ XÉT NGHIỆM</span>
                      <div className="flex items-center gap-10">
                        <span>KẾT QUẢ</span>
                        <span className="w-24 text-right">THAM CHIẾU</span>
                      </div>
                    </div>

                    {/* Interactive Bounding Box Rows */}
                    <div className="space-y-3">
                      {ocrFacts.map((fact, idx) => {
                        const isSelected = selectedOcrFact === idx;
                        return (
                          <div
                            key={fact.id}
                            onClick={() => setSelectedOcrFact(idx)}
                            className={`relative flex items-center justify-between p-3.5 rounded-xl cursor-pointer transition-all duration-300 ${
                              isSelected
                                ? 'border-2 border-teal-400 bg-teal-400/15 text-white shadow-[0_0_25px_rgba(45,212,191,0.35)] ring-1 ring-teal-400/50'
                                : 'border border-white/5 hover:bg-white/5 hover:border-white/15 text-slate-300'
                            }`}
                          >
                            {/* Bounding Box Floating Badge */}
                            {isSelected && (
                              <div className="absolute -top-3.5 left-3 flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-teal-400 text-black text-[10px] font-bold font-mono uppercase tracking-wider shadow-lg">
                                <span className="w-1.5 h-1.5 rounded-full bg-black animate-pulse" />
                                <span>BBOX GROUNDED: {fact.coords}</span>
                              </div>
                            )}

                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-mono text-slate-500">0{idx + 1}.</span>
                              <span className="font-semibold text-sm sm:text-base">{fact.name}</span>
                            </div>

                            <div className="flex items-center gap-10">
                              <span className="font-bold font-mono text-base sm:text-lg text-teal-300">{fact.value}</span>
                              <span className="text-xs sm:text-sm text-slate-400 w-24 text-right">{fact.ref}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Document Footer Bar */}
                    <div className="mt-5 pt-3 border-t border-white/10 flex items-center justify-between text-[11px] text-slate-400">
                      <span>Bác sĩ chỉ định: <span className="text-slate-200">PGS.TS. Trần Quốc H.</span></span>
                      <span className="font-mono text-teal-400">Độ tin cậy OCR: 99.8%</span>
                    </div>

                  </div>
                </div>

                {/* Right: Extracted Facts Card */}
                <div className="lg:col-span-5 space-y-4">
                  <h4 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-teal-400" />
                    Thực Thể Được AI Trích Xuất &amp; Xác Thực
                  </h4>

                  <div className="space-y-3.5">
                    {ocrFacts.map((fact, idx) => (
                      <div
                        key={fact.id}
                        onClick={() => setSelectedOcrFact(idx)}
                        className={`p-5 rounded-xl cursor-pointer transition-all oura-glass-card ${selectedOcrFact === idx
                            ? 'border-teal-500/50 bg-teal-950/30'
                            : 'hover:border-white/10'
                          }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-semibold text-sm sm:text-base text-slate-100">{fact.name}</span>
                          <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${fact.statusClass}`}>
                            {fact.status}
                          </span>
                        </div>
                        <div className="text-lg font-bold font-mono text-teal-300 mb-1">
                          {fact.value} <span className="text-xs font-normal text-slate-400">(Tham chiếu: {fact.ref})</span>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-400 font-normal">{fact.docNote}</p>
                      </div>
                    ))}
                  </div>

                  <div className="p-4 rounded-xl bg-teal-950/20 border border-teal-500/20 text-xs sm:text-sm text-teal-300/90 leading-relaxed">
                    💡 Bác sĩ có thể nhấp vào bất kỳ thông số nào để đối soát tức thời tọa độ trên bản scan PDF gốc, hoàn toàn loại bỏ nguy cơ đọc sai sót.
                  </div>
                </div>

              </div>
            )}

            {/* TAB 2: TIMELINE STREAM */}
            {activeSandboxTab === 'timeline' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-white/5">
                  <div>
                    <h4 className="text-lg font-semibold text-slate-100">Chuỗi Sự Kiện Lâm Sàng (2024 — 2026)</h4>
                    <p className="text-sm text-slate-400">Tự động xâu chuỗi 34 lượt khám ngoại trú, xét nghiệm máu và đợt chỉnh liều thuốc</p>
                  </div>

                  <div className="flex items-center gap-2">
                    {([2024, 2025, 2026] as const).map((year) => (
                      <button
                        key={year}
                        onClick={() => setTimelineYear(year)}
                        className={`px-5 py-2 rounded-full text-xs sm:text-sm font-mono font-medium transition-all ${timelineYear === year
                            ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
                            : 'text-slate-400 hover:text-white'
                          }`}
                      >
                        Năm {year}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Timeline Visual Stream */}
                <div className="space-y-4">

                  {/* Event 1 */}
                  <div className="flex items-start gap-5 p-6 rounded-2xl oura-glass-card">
                    <div className="w-12 h-12 rounded-full bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-300 shrink-0">
                      <Stethoscope className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between text-base mb-1.5">
                        <span className="font-semibold text-slate-100">Tái Khám Định Kỳ — ĐTĐ &amp; Tăng Huyết Áp</span>
                        <span className="font-mono text-slate-400 text-xs sm:text-sm">15/01/2026</span>
                      </div>
                      <p className="text-sm sm:text-base text-slate-300 leading-relaxed mb-3">
                        Bác sĩ đánh giá đáp ứng sau 3 tháng chỉnh liều. HbA1c giảm về 7.4%, HA ổn định 138/84 mmHg.
                      </p>
                      <div className="flex flex-wrap gap-2 text-xs sm:text-sm">
                        <span className="px-3 py-1 rounded-full oura-pill text-teal-300">HbA1c: 7.4%</span>
                        <span className="px-3 py-1 rounded-full oura-pill text-emerald-300">HA: 138/84 mmHg</span>
                        <span className="px-3 py-1 rounded-full oura-pill text-slate-400">Metformin 1000mg</span>
                      </div>
                    </div>
                  </div>

                  {/* Event 2 */}
                  <div className="flex items-start gap-5 p-6 rounded-2xl oura-glass-card">
                    <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-300 shrink-0">
                      <AlertTriangle className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between text-base mb-1.5">
                        <span className="font-semibold text-slate-100">Điều Chỉnh Liều Thuốc — Kháng Trị HbA1c</span>
                        <span className="font-mono text-slate-400 text-xs sm:text-sm">10/01/2026</span>
                      </div>
                      <p className="text-sm sm:text-base text-slate-300 leading-relaxed mb-3">
                        HbA1c tăng vọt lên 8.2%. Tăng liều Metformin từ 500mg lên 1000mg/ngày (chia 2 lần).
                      </p>
                      <div className="flex flex-wrap gap-2 text-xs sm:text-sm">
                        <span className="px-3 py-1 rounded-full oura-pill text-rose-300">HbA1c: 8.2% (Tăng)</span>
                        <span className="px-3 py-1 rounded-full oura-pill text-amber-300">Tăng liều +500mg</span>
                      </div>
                    </div>
                  </div>

                  {/* Event 3 */}
                  <div className="flex items-start gap-5 p-6 rounded-2xl oura-glass-card">
                    <div className="w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-300 shrink-0">
                      <FileSignature className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between text-base mb-1.5">
                        <span className="font-semibold text-slate-100">Khám Chuyên Khoa Tim Mạch &amp; Khởi Trị Thuốc HA</span>
                        <span className="font-mono text-slate-400 text-xs sm:text-sm">10/06/2024</span>
                      </div>
                      <p className="text-sm sm:text-base text-slate-300 leading-relaxed mb-3">
                        Ghi nhận HA 158/94 mmHg. Bắt đầu dùng Amlodipine 5mg/ngày và tư vấn tiết chế giảm muối.
                      </p>
                      <div className="flex flex-wrap gap-2 text-xs sm:text-sm">
                        <span className="px-3 py-1 rounded-full oura-pill text-cyan-300">Khởi đầu: Amlodipine 5mg</span>
                      </div>
                    </div>
                  </div>

                </div>
              </div>
            )}

            {/* TAB 3: ASK THE CHART AI */}
            {activeSandboxTab === 'ask' && (
              <div className="grid lg:grid-cols-12 gap-10 items-start">

                {/* Left: Sample Questions */}
                <div className="lg:col-span-5 space-y-3.5">
                  <h4 className="text-base font-semibold text-slate-100 mb-2">Câu Hỏi Mẫu Bác Sĩ Hay Truy Vấn:</h4>

                  {askPrompts.map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => setActivePromptIndex(idx)}
                      className={`w-full text-left p-4 rounded-xl transition-all oura-glass-card ${activePromptIndex === idx
                          ? 'border-teal-500/50 bg-teal-950/30 text-white'
                          : 'text-slate-300 hover:text-white'
                        }`}
                    >
                      <div className="text-sm sm:text-base font-medium">{p.q}</div>
                    </button>
                  ))}

                  <div className="pt-2 text-xs sm:text-sm text-slate-400">
                    🔍 AI Co-pilot hỗ trợ hỏi đáp tự nhiên trên toàn bộ hồ sơ với thuật toán tìm kiếm kết hợp Hybrid Fusion (BM25 + Semantic Vector).
                  </div>
                </div>

                {/* Right: AI Answer & Grounded Citations */}
                <div className="lg:col-span-7 space-y-4">
                  <div className="p-7 rounded-2xl bg-teal-950/20 border border-teal-500/20 space-y-4">
                    <div className="flex items-center gap-2.5 text-base font-semibold text-teal-200">
                      <Bot className="w-6 h-6 text-teal-400" />
                      <span>Câu Trả Lời Của AI Clinical Copilot</span>
                    </div>

                    <p className="text-base sm:text-lg text-slate-200 leading-relaxed">
                      {askPrompts[activePromptIndex].a}
                    </p>

                    <div className="pt-4 border-t border-white/5 space-y-2">
                      <div className="text-xs sm:text-sm font-semibold text-slate-400">Bằng chứng &amp; Dẫn chứng gốc:</div>
                      <div className="flex flex-wrap gap-2.5">
                        {askPrompts[activePromptIndex].citations.map((cit, cIdx) => (
                          <span key={cIdx} className="px-3.5 py-1 rounded-full oura-pill text-xs sm:text-sm text-teal-300 bg-teal-500/10 border border-teal-500/30">
                            {cit}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            )}

          </div>

        </section>

        {/* 6. ACADEMIC & CLINICAL GOVERNANCE BOARD */}
        <section className="py-16 sm:py-24 scroll-mt-20 border-t border-white/10 text-center">
          <div className="max-w-5xl mx-auto mb-12 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full oura-pill px-4 py-1.5 text-xs font-medium text-teal-300 tracking-widest uppercase">
              <Award className="h-4 w-4" />
              <span>Tiêu chuẩn &amp; Chứng thực y khoa</span>
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-100 tracking-tight">
              Xây Dựng Trên Nền Tảng Khoa Học Vững Chắc
            </h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-5">
            {standards.map((st, idx) => (
              <div key={idx} className="p-6 rounded-xl oura-glass-card text-center space-y-2">
                <div className="text-base font-semibold text-slate-100">{st.name}</div>
                <div className="text-xs sm:text-sm text-slate-400 font-normal leading-snug">{st.desc}</div>
              </div>
            ))}
          </div>
        </section>

      </main>

      {/* 7. FOOTER */}
      <footer className="border-t border-white/10 py-12 px-4 sm:px-10 text-sm text-slate-400 bg-black/40">
        <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-300">
              <Stethoscope className="w-4 h-4" />
            </div>
            <span>Clinical Review Copilot — AI Rà Soát Bệnh Án Dọc</span>
          </div>

          <div>
            Hệ thống hỗ trợ quyết định lâm sàng (CDSS) tuân thủ tiêu chuẩn HL7 FHIR R4 &amp; HITL.
          </div>
        </div>
      </footer>

    </div>
  );
}
