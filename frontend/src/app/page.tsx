'use client';

import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[#F9FAFB] text-slate-800 relative overflow-x-hidden font-sans">
      {/* Subtle Grid Background */}
      <div 
        className="absolute inset-0 z-0 pointer-events-none opacity-[0.4]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0h40v40H0V0zm1 1h38v38H1V1z' fill='%23e5e7eb' fill-opacity='0.4' fill-rule='evenodd'/%3E%3C/svg%3E")`
        }}
      />

      {/* Navbar */}
      <header className="relative z-10 w-full max-w-[1200px] mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5 cursor-pointer">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-[#4F46E5] shadow-lg shadow-indigo-500/20">
            <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          <span className="font-extrabold text-[22px] tracking-tight text-slate-800">
            Clinical AI
          </span>
        </div>
        
        <nav className="hidden md:flex items-center gap-10 text-[15px] font-semibold text-slate-500">
          <Link href="#" className="text-indigo-600">Trang chủ</Link>
          <Link href="#" className="hover:text-slate-900 transition">Tính năng</Link>
          <Link href="#" className="hover:text-slate-900 transition">Cách hoạt động</Link>
          <Link href="#" className="hover:text-slate-900 transition">Liên hệ</Link>
        </nav>

        <div className="flex items-center gap-3">
          <Link href="/login" className="hidden md:block text-[15px] font-semibold text-slate-600 hover:text-slate-900 transition px-4 py-2">
            Đăng nhập
          </Link>
          <Link href="/login" className="text-[15px] font-semibold bg-[#4F46E5] hover:bg-[#4338CA] text-white px-6 py-2.5 rounded-full shadow-lg shadow-indigo-500/30 transition-all active:scale-95">
            Đăng ký
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 w-full max-w-[1200px] mx-auto px-6 pt-12 md:pt-20 pb-20 grid lg:grid-cols-2 gap-12 lg:gap-8 items-center">
        
        {/* Left Content */}
        <div className="max-w-[600px] z-20">
          <h1 className="text-[2.5rem] leading-[1.3] md:text-[3.75rem] font-bold text-[#111827] tracking-tight mb-6">
            Tối ưu thời gian, <br /> 
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#4F46E5] to-[#06B6D4] font-extrabold">
              chẩn đoán chính xác
            </span>
          </h1>
          
          <p className="text-lg text-slate-500 mb-8 max-w-[480px] leading-[1.6]">
            Hệ thống AI tự động phân tích hàng trăm trang hồ sơ bệnh án, giúp bác sĩ đưa ra quyết định nhanh chóng, chính xác.
          </p>

          <div className="flex flex-wrap items-center gap-4 mb-12">
            <Link href="/login" className="flex items-center gap-2 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-[15px] font-semibold px-8 py-3.5 rounded-full shadow-xl shadow-indigo-500/20 transition-all active:scale-95">
              Trải nghiệm ngay
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </Link>
            <button className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 text-[15px] font-semibold px-8 py-3.5 rounded-full border border-slate-200 transition-all shadow-sm">
              Tìm hiểu thêm
            </button>
          </div>

          {/* Stats Card */}
          <div className="bg-white rounded-2xl p-6 md:p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 flex flex-wrap items-center gap-8 md:gap-12 w-max">
            <div>
              <div className="text-4xl md:text-5xl font-extrabold text-[#4F46E5] mb-2 tracking-tighter">98%</div>
              <div className="text-[13px] text-slate-500 font-medium leading-tight">Độ chính xác trong<br/>trích xuất dữ liệu</div>
            </div>
            <div className="w-px h-16 bg-slate-100 hidden md:block"></div>
            <div>
              <div className="text-4xl md:text-5xl font-extrabold text-[#4F46E5] mb-2 tracking-tighter">x3,5</div>
              <div className="text-[13px] text-slate-500 font-medium leading-tight">Tốc độ tiếp thu<br/>tiền sử bệnh lý</div>
            </div>
          </div>
        </div>

        {/* Right Content (Mascots & Cards) */}
        <div className="relative w-full h-[450px] md:h-[550px] lg:h-[600px] mt-10 lg:mt-0">
          
          {/* Subtle Glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-gradient-to-tr from-[#4F46E5]/10 to-[#06B6D4]/10 rounded-full blur-[80px] pointer-events-none"></div>

          {/* AI Robot Framed Card */}
          <div className="absolute top-0 right-0 w-[65%] max-w-[340px] bg-white rounded-[2rem] p-2.5 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] z-10 animate-[float_6s_ease-in-out_infinite]">
            <div className="w-full aspect-square rounded-[1.5rem] overflow-hidden bg-slate-50">
              <img 
                src="/hero-3d.png" 
                alt="AI Robot Mascot" 
                className="w-full h-full object-cover mix-blend-multiply hover:scale-105 transition-transform duration-700" 
              />
            </div>
          </div>

          {/* Doctor Framed Card */}
          <div className="absolute bottom-28 left-0 w-[55%] max-w-[280px] bg-white rounded-[2rem] p-2.5 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.15)] z-20 animate-[float_5s_ease-in-out_infinite_reverse]" style={{ animationDelay: '1s' }}>
            <div className="w-full aspect-[4/5] rounded-[1.5rem] overflow-hidden bg-slate-50 relative">
              <img 
                src="/doctor-3d.png" 
                alt="Doctor Mascot" 
                className="w-full h-full object-cover scale-[1.1] translate-y-3 mix-blend-multiply hover:scale-125 transition-transform duration-700" 
              />
            </div>
          </div>

          {/* Floating UI Card */}
          <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 md:-bottom-8 md:left-auto md:right-8 md:translate-x-0 z-30 w-[90%] max-w-[340px] bg-white/95 backdrop-blur-xl rounded-[24px] p-5 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.15)] border border-white/60 animate-[float_4s_ease-in-out_infinite]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-800 text-[15px]">Phân tích tự động</h3>
              <span className="text-[10px] font-bold bg-[#ECFDF5] text-[#059669] px-2.5 py-1 rounded-full uppercase tracking-wider">Hoàn tất</span>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-start gap-3 bg-slate-50/80 p-3 rounded-[16px] border border-slate-100">
                <div className="w-5 h-5 rounded-full bg-[#E0E7FF] flex items-center justify-center text-[#4F46E5] mt-0.5 shrink-0">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7"></path></svg>
                </div>
                <div>
                  <div className="text-[13px] font-bold text-slate-700">Tìm thấy 3 tương tác thuốc</div>
                  <div className="text-[11px] text-slate-500 mt-0.5 font-medium">Paracetamol & Warfarin cần lưu ý.</div>
                </div>
              </div>
              
              <div className="flex items-start gap-3 bg-slate-50/80 p-3 rounded-[16px] border border-slate-100">
                <div className="w-5 h-5 rounded-full bg-[#E0E7FF] flex items-center justify-center text-[#4F46E5] mt-0.5 shrink-0">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7"></path></svg>
                </div>
                <div>
                  <div className="text-[13px] font-bold text-slate-700">Tóm tắt tiểu sử bệnh lý</div>
                  <div className="text-[11px] text-slate-500 mt-0.5 font-medium">Cao huyết áp, Tiểu đường.</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <style dangerouslySetInnerHTML={{__html: `
        :root { color-scheme: light; }
        body { background: #F9FAFB !important; color: #1e293b !important; }
        @keyframes float {
          0% { transform: translateY(0px); }
          50% { transform: translateY(-12px); }
          100% { transform: translateY(0px); }
        }
      `}} />
    </div>
  );
}
