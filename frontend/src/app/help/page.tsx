'use client';

import { useState } from 'react';
import { HelpCircle, Book, MessageSquare, ExternalLink, Search, Mail, ChevronDown, ChevronUp, CheckCircle2, Bot, X } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';

export default function HelpPage() {
  const { t } = useLanguage();
  const [searchQuery, setSearchQuery] = useState('');
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [showDocsModal, setShowDocsModal] = useState(false);
  const [showChatModal, setShowChatModal] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<{ role: 'bot' | 'user', text: string }[]>([
    { role: 'bot', text: 'Xin chào Bác sĩ! Tôi là Trợ lý Hỗ trợ Kỹ thuật Clinical Copilot. Bác sĩ cần giải đáp thắc mắc gì về cách sử dụng hệ thống?' }
  ]);

  const faqs = [
    {
      q: 'Làm thế nào để tải lên và phân tích hồ sơ bệnh án mới?',
      a: 'Bác sĩ truy cập mục "Quản lý Hồ sơ" (Case Files) trên thanh menu hoặc từ Bảng điều khiển. Chọn tệp PDF đơn thuốc scan, kết quả xét nghiệm hoặc tệp FHIR JSON rồi bấm "Tiến hành tải lên". Hệ thống sẽ tự động chạy OCR, bóc tách thực thể và đồng bộ vào biểu đồ.',
    },
    {
      q: 'Hệ thống đối soát chứng cứ y khoa (Evidence Grounding) hoạt động ra sao?',
      a: 'Mỗi nhận định trong Bản tóm tắt điều trị (SOAP Summary) đều được gắn kèm Bounding Box hoặc mã trích dẫn nguồn. Bác sĩ bấm vào tag bằng chứng để mở tài liệu PDF gốc hoặc bản ghi FHIR để xác thực trực tiếp trước khi phê duyệt.',
    },
    {
      q: 'Cơ chế chống ảo giác (Fail-Closed Guardrail) là gì?',
      a: 'Nếu AI không tìm thấy đủ chứng cứ xác thực trong dữ liệu bệnh nhân hoặc phát hiện mâu thuẫn đối kháng giữa các nguồn, hệ thống sẽ tự động gắn cờ cảnh báo (Flag) thay vì tự suy đoán, đảm bảo an toàn tuyệt đối cho quyết định điều trị.',
    },
    {
      q: 'Dữ liệu bệnh nhân có được bảo mật và tuân thủ HIPAA không?',
      a: 'Toàn bộ dữ liệu bệnh nhân được ẩn danh hóa (De-identification), mã hóa theo chuẩn AES-256 (At-Rest) và TLS 1.3 (In-Transit). Mọi thao tác ký duyệt và chỉnh sửa đều được lưu vết trong Nhật ký Tuân thủ (Audit Log).',
    },
    {
      q: 'Làm thế nào để xuất file tóm tắt bệnh án PDF và Hướng dẫn bệnh nhân (Care Plan)?',
      a: 'Trong giao diện xem chi tiết bệnh nhân, ở chân trang có 2 nút: "Hướng Dẫn Bệnh Nhân (Care Plan)" để tạo tờ rơi dặn dò dễ hiểu cho người bệnh, và "Xuất File Bệnh án PDF" để in hoặc lưu trữ hồ sơ chính thức.',
    }
  ];

  const filteredFaqs = faqs.filter(
    f => f.q.toLowerCase().includes(searchQuery.toLowerCase()) || f.a.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSendSupportChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const userMsg = chatInput.trim();
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setChatInput('');
    setTimeout(() => {
      setChatMessages(prev => [
        ...prev,
        { role: 'bot', text: `Cảm ơn Bác sĩ đã gửi câu hỏi: "${userMsg}". Yêu cầu đã được ghi nhận vào hệ thống hỗ trợ kỹ thuật và đội ngũ chuyên gia sẽ phản hồi sớm nhất.` }
      ]);
    }, 800);
  };

  return (
    <div className="page-content space-y-8 flex-1 h-full overflow-y-auto">
      {/* Page Header */}
      <div className="flex flex-col items-center justify-center border-b pb-8 pt-4 text-center" style={{ borderColor: 'var(--border-card)' }}>
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center border shadow-sm mb-4" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
          <HelpCircle className="w-7 h-7" />
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">{t('help.title')}</h1>
        <p className="text-sm mt-2 max-w-md" style={{ color: 'var(--text-muted)' }}>{t('help.subtitle')}</p>
        
        {/* Search input */}
        <div className="relative w-full max-w-xl mt-6">
          <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input 
            type="text" 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm tài liệu, câu hỏi thường gặp..." 
            className="clinical-input w-full pl-11 pr-4 py-3 text-xs font-semibold shadow-sm"
          />
        </div>
      </div>

      {/* 3 Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        
        {/* Card 1: Docs */}
        <div className="clinical-card p-6 flex flex-col group transition-all hover:-translate-y-1 hover:shadow-md">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4 border" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
            <Book className="w-5 h-5" />
          </div>
          <h3 className="text-base font-extrabold text-slate-900 dark:text-slate-100 mb-1">{t('help.docs')}</h3>
          <p className="text-xs mb-5 flex-1 font-medium" style={{ color: 'var(--text-muted)' }}>{t('help.docsDesc')}</p>
          <button 
            onClick={() => setShowDocsModal(true)}
            className="flex items-center gap-1.5 text-xs font-bold transition-colors mt-auto cursor-pointer"
            style={{ color: 'var(--accent-teal)' }}
          >
            <span>{t('help.docsAction')}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Card 2: Live Chat */}
        <div className="clinical-card p-6 flex flex-col group transition-all hover:-translate-y-1 hover:shadow-md">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4 border bg-cyan-50 dark:bg-cyan-500/15 border-cyan-200 dark:border-cyan-500/30 text-cyan-600 dark:text-cyan-300">
            <MessageSquare className="w-5 h-5" />
          </div>
          <h3 className="text-base font-extrabold text-slate-900 dark:text-slate-100 mb-1">{t('help.chat')}</h3>
          <p className="text-xs mb-5 flex-1 font-medium" style={{ color: 'var(--text-muted)' }}>{t('help.chatDesc')}</p>
          <button 
            onClick={() => setShowChatModal(true)}
            className="flex items-center gap-1.5 text-xs font-bold text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 transition-colors mt-auto cursor-pointer"
          >
            <span>{t('help.chatAction')}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Card 3: Email */}
        <div className="clinical-card p-6 flex flex-col group transition-all hover:-translate-y-1 hover:shadow-md">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4 border bg-purple-50 dark:bg-purple-500/15 border-purple-200 dark:border-purple-500/30 text-purple-600 dark:text-purple-300">
            <Mail className="w-5 h-5" />
          </div>
          <h3 className="text-base font-extrabold text-slate-900 dark:text-slate-100 mb-1">{t('help.email')}</h3>
          <p className="text-xs mb-5 flex-1 font-medium" style={{ color: 'var(--text-muted)' }}>{t('help.emailDesc')}</p>
          <a 
            href="mailto:support@clinicalcopilot.health?subject=Yeu%20Cau%20Ho%20Tro%20Clinical%20Copilot"
            className="flex items-center gap-1.5 text-xs font-bold text-purple-600 dark:text-purple-400 hover:text-purple-700 transition-colors mt-auto cursor-pointer"
          >
            <span>{t('help.emailAction')}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

      </div>

      {/* FAQ Accordion Section */}
      <div className="clinical-card p-6 sm:p-8 space-y-5">
        <h2 className="text-lg font-extrabold text-slate-900 dark:text-slate-100">{t('help.faq')}</h2>
        
        <div className="space-y-3">
          {filteredFaqs.length === 0 ? (
            <div className="text-center py-8 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
              Không tìm thấy câu hỏi phù hợp với từ khóa "{searchQuery}".
            </div>
          ) : (
            filteredFaqs.map((faq, idx) => {
              const isOpen = openFaq === idx;
              return (
                <div 
                  key={idx}
                  className="clinical-subcard rounded-xl border overflow-hidden transition-all"
                  style={{ borderColor: 'var(--border-card)' }}
                >
                  <button
                    type="button"
                    onClick={() => setOpenFaq(isOpen ? null : idx)}
                    className="w-full p-4 flex items-center justify-between gap-4 text-left cursor-pointer transition-colors"
                  >
                    <span className="text-xs sm:text-sm font-bold text-slate-900 dark:text-slate-100 flex-1">
                      {faq.q}
                    </span>
                    <div className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0 border" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--accent-teal)' }}>
                      {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </div>
                  </button>

                  {isOpen && (
                    <div className="px-4 pb-4 pt-1 text-xs sm:text-sm leading-relaxed border-t font-medium" style={{ borderColor: 'var(--border-card)', color: 'var(--text-secondary)' }}>
                      {faq.a}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* DOCS MODAL */}
      {showDocsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="clinical-card w-full max-w-2xl p-6 space-y-4 shadow-2xl relative max-h-[85vh] overflow-y-auto chat-scrollbar">
            <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: 'var(--border-card)' }}>
              <div className="flex items-center gap-2">
                <Book className="w-5 h-5 text-teal-600 dark:text-teal-400" />
                <h3 className="text-base font-extrabold text-slate-900 dark:text-slate-100">Hướng dẫn Sử dụng Hệ thống</h3>
              </div>
              <button onClick={() => setShowDocsModal(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-400 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs leading-relaxed text-slate-800 dark:text-slate-200">
              <div className="space-y-1">
                <h4 className="font-bold text-sm text-teal-700 dark:text-teal-300">1. Quy trình Rà soát Hồ sơ (Clinical Review Flow)</h4>
                <p>Bác sĩ mở danh sách bệnh nhân, chọn một hồ sơ cần đánh giá. AI sẽ tổng hợp bản thảo SOAP kèm đối soát mâu thuẫn liều thuốc và diễn tiến các chỉ số xét nghiệm then chốt.</p>
              </div>

              <div className="space-y-1">
                <h4 className="font-bold text-sm text-teal-700 dark:text-teal-300">2. Cơ chế Xác thực Nguồn (Grounding &amp; Citations)</h4>
                <p>Mỗi luận điểm đều có gắn tag nguồn. Nhấp chuột vào tag để mở tài liệu PDF scan gốc với Bounding Box tô đậm khu vực trích xuất dữ liệu.</p>
              </div>

              <div className="space-y-1">
                <h4 className="font-bold text-sm text-teal-700 dark:text-teal-300">3. Phê duyệt &amp; Xuất bản (HitL Approval &amp; Export)</h4>
                <p>Bác sĩ có thể chỉnh sửa trực tiếp nội dung nếu cần, sau đó bấm <strong>Phê duyệt chuyên môn</strong> để lưu vào bộ nhớ lâm sàng bệnh nhân hoặc xuất File PDF in.</p>
              </div>
            </div>

            <div className="pt-3 border-t flex justify-end" style={{ borderColor: 'var(--border-card)' }}>
              <button onClick={() => setShowDocsModal(false)} className="px-4 py-2 bg-teal-600 text-white font-bold text-xs rounded-xl cursor-pointer hover:bg-teal-700">
                Đã hiểu
              </button>
            </div>
          </div>
        </div>
      )}

      {/* LIVE CHAT SUPPORT MODAL */}
      {showChatModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="clinical-card w-full max-w-lg flex flex-col h-[520px] shadow-2xl relative overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b flex items-center justify-between shrink-0" style={{ borderColor: 'var(--border-card)' }}>
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl flex items-center justify-center border" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">Hỗ trợ Kỹ thuật Trực tuyến</h3>
                  <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Đang hoạt động
                  </p>
                </div>
              </div>
              <button onClick={() => setShowChatModal(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-400 cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 p-4 overflow-y-auto space-y-3 chat-scrollbar">
              {chatMessages.map((m, idx) => (
                <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                    m.role === 'user' 
                      ? 'bg-teal-600 text-white font-semibold rounded-tr-none' 
                      : 'clinical-subcard text-slate-900 dark:text-slate-100 rounded-tl-none border shadow-sm font-medium'
                  }`}>
                    {m.text}
                  </div>
                </div>
              ))}
            </div>

            {/* Input */}
            <form onSubmit={handleSendSupportChat} className="p-3 border-t flex gap-2" style={{ borderColor: 'var(--border-card)' }}>
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Nhập câu hỏi hỗ trợ..."
                className="clinical-input flex-1 px-3 py-2 text-xs font-medium"
              />
              <button type="submit" className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl cursor-pointer">
                Gửi
              </button>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
