'use client';

import React, { useState, useRef, useEffect } from 'react';
import { patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { Send, Bot, User, AlertCircle, XCircle, Trash2, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

/**
 * Enhanced Markdown renderer for clinical chat responses,
 * supporting tables, headings, lists, inline bolding, and code tags.
 */
function MarkdownRenderer({ content }: { content: string }) {
  if (!content) return null;

  // Split lines into blocks
  const lines = content.split('\n');
  const blocks: { type: 'table' | 'text', lines: string[] }[] = [];
  let currentBlock: { type: 'table' | 'text', lines: string[] } | null = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const isTableLine = line.trim().startsWith('|') && line.trim().endsWith('|');

    if (isTableLine) {
      if (!currentBlock || currentBlock.type !== 'table') {
        if (currentBlock) blocks.push(currentBlock);
        currentBlock = { type: 'table', lines: [line] };
      } else {
        currentBlock.lines.push(line);
      }
    } else {
      if (!currentBlock || currentBlock.type !== 'text') {
        if (currentBlock) blocks.push(currentBlock);
        currentBlock = { type: 'text', lines: [line] };
      } else {
        currentBlock.lines.push(line);
      }
    }
  }
  if (currentBlock) blocks.push(currentBlock);

  const renderInline = (text: string) => {
    // Regex for bold **text** and code `text`
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={idx} className="font-extrabold text-slate-950 dark:text-white">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={idx} className="px-1.5 py-0.5 rounded border font-mono text-[11px]" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
            {part.slice(1, -1)}
          </code>
        );
      }
      return <React.Fragment key={idx}>{part}</React.Fragment>;
    });
  };

  return (
    <div className="space-y-2 text-xs leading-relaxed text-slate-900 dark:text-slate-100">
      {blocks.map((block, bIdx) => {
        if (block.type === 'table') {
          const rows = block.lines
            .map(l => l.trim().split('|').slice(1, -1).map(c => c.trim()))
            .filter(r => r.length > 0);

          if (rows.length < 2) return null;

          const headerRow = rows[0];
          const dataRows = rows.slice(2);

          return (
            <div key={bIdx} className="overflow-x-auto my-3 rounded-xl border shadow-sm" style={{ borderColor: 'var(--border-card)', backgroundColor: 'var(--bg-card)' }}>
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b" style={{ backgroundColor: 'var(--bg-subcard)', borderColor: 'var(--border-card)', color: 'var(--accent-teal)' }}>
                    {headerRow.map((cell, cIdx) => (
                      <th key={cIdx} className="px-3 py-2.5 font-bold uppercase tracking-wider text-[11px] whitespace-nowrap">
                        {renderInline(cell)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--border-card)' }}>
                  {dataRows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className="transition-colors hover:bg-[var(--accent-teal-bg)]"
                    >
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3 py-2 text-slate-900 dark:text-slate-100 whitespace-normal">
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        // Text block: parse headings, lists, paragraphs
        return (
          <div key={bIdx} className="space-y-1">
            {block.lines.map((line, lIdx) => {
              const trimmed = line.trim();
              if (!trimmed) return <div key={lIdx} className="h-1" />;

              if (trimmed.startsWith('### ')) {
                return (
                  <h4 key={lIdx} className="font-bold text-sm mt-2 mb-1 flex items-center gap-1.5" style={{ color: 'var(--accent-teal)' }}>
                    {renderInline(trimmed.replace('### ', ''))}
                  </h4>
                );
              }

              if (trimmed.startsWith('## ')) {
                return (
                  <h3 key={lIdx} className="font-extrabold text-base mt-2 mb-1 flex items-center gap-1.5" style={{ color: 'var(--accent-teal)' }}>
                    {renderInline(trimmed.replace('## ', ''))}
                  </h3>
                );
              }

              if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                return (
                  <div key={lIdx} className="flex items-start gap-2 pl-1 my-0.5">
                    <span className="mt-0.5 font-bold" style={{ color: 'var(--accent-teal)' }}>•</span>
                    <span className="flex-1 font-medium">{renderInline(trimmed.slice(2))}</span>
                  </div>
                );
              }

              return (
                <p key={lIdx} className="my-0.5 font-medium">
                  {renderInline(trimmed)}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

export default function ChatPanel({ patientId }: { patientId: string }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant', text: string, status?: string, citations?: any[] }[]>([]);
  const { setFocusedCitation } = useAppStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const quickPrompts = [
    { label: '💊 Diễn tiến Thuốc & Phác đồ', text: 'Quá trình sử dụng thuốc của bệnh nhân qua các đợt khám thay đổi như thế nào?' },
    { label: '⚠️ Đối soát Mâu thuẫn Liều', text: 'Có bất kỳ mâu thuẫn hay xung đột liều thuốc nào giữa các nguồn dữ liệu không?' },
    { label: '📉 Xu hướng HbA1c & Đường huyết', text: 'Chỉ số HbA1c và đường huyết gần đây biến động ra sao và can thiệp điều chỉnh thế nào?' },
    { label: '🛡️ Tiền sử & Dị ứng Thuốc', text: 'Bệnh nhân có tiền sử dị ứng thuốc gì không và được ghi nhận ở tài liệu nào?' }
  ];

  const handleAskWithText = async (questionText: string) => {
    if (!questionText.trim() || loading) return;

    const userQuery = questionText.trim();
    setMessages(prev => [...prev, { role: 'user', text: userQuery }]);
    setQuery('');
    setLoading(true);

    try {
      const res = await patients.ask(patientId, userQuery);
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: res.answer || res.message || 'No clear answer provided.',
        status: res.status,
        citations: res.citations
      }]);
    } catch (err: any) {
      let detail = err.detail || err;
      if (typeof detail === 'string' && detail.trim().startsWith('{')) {
        try {
          detail = JSON.parse(detail);
        } catch {
          /* ignore */
        }
      }

      let textToDisplay = '⚠️ Không thể truy xuất dữ liệu lúc này. Vui lòng thử lại sau.';
      if (typeof detail === 'object' && detail?.message) {
        textToDisplay = detail.message;
      } else if (typeof detail === 'string' && detail && !detail.startsWith('{')) {
        textToDisplay = detail;
      }

      setMessages(prev => [...prev, {
        role: 'assistant',
        text: textToDisplay,
        status: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleAsk = () => {
    handleAskWithText(query);
  };

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

  return (
    <div className="clinical-card overflow-hidden flex flex-col h-full min-h-0 shadow-lg">
      {/* Header */}
      <div className="p-3.5 px-4 flex items-center justify-between shrink-0 border-b" style={{ borderColor: 'var(--border-card)', backgroundColor: 'var(--bg-card)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center border shadow-sm" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold tracking-tight" style={{ color: 'var(--accent-teal)' }}>
              AI Co-pilot Lâm sàng
            </h3>
            <p className="text-[10px] font-mono font-medium" style={{ color: 'var(--text-muted)' }}>Grounded Clinical Reasoning</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="p-1.5 rounded-lg border text-xs transition-colors hover:text-rose-600 hover:bg-rose-50"
              style={{ borderColor: 'var(--border-card)', color: 'var(--text-muted)' }}
              title="Xóa cuộc trò chuyện"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 chat-scrollbar pr-2">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center space-y-4 py-8 px-4">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center border shadow-sm" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
              <Bot className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h4 className="text-base font-extrabold text-slate-900 dark:text-slate-100">Trợ lý Hỏi - Đáp Lâm sàng</h4>
              <p className="text-xs max-w-sm leading-relaxed font-medium" style={{ color: 'var(--text-secondary)' }}>
                Hỏi trực tiếp về diễn tiến, xét nghiệm, chẩn đoán, thuốc hoặc chọn câu hỏi nhanh bên dưới:
              </p>
            </div>

            {/* Quick Prompts Chips */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md pt-2">
              {quickPrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => handleAskWithText(p.text)}
                  disabled={loading}
                  className="clinical-subcard text-left p-3 flex flex-col gap-0.5 shadow-sm group cursor-pointer transition-all hover:scale-[1.01]"
                >
                  <span className="font-bold text-xs" style={{ color: 'var(--accent-teal)' }}>{p.label}</span>
                  <span className="text-[11px] font-medium line-clamp-1" style={{ color: 'var(--text-secondary)' }}>{p.text}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            key={idx}
            className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${
              msg.role === 'user' 
                ? 'bg-teal-600 text-white border-teal-700 font-bold' 
                : 'border'
            }`} style={msg.role !== 'user' ? { backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' } : {}}>
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`max-w-[92%] rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${
              msg.role === 'user'
                ? 'bg-teal-600 text-white font-semibold rounded-tr-none shadow-sm'
                : 'clinical-subcard rounded-tl-none shadow-sm'
            }`}>

              {msg.status === 'not_found' && (
                <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 mb-2 font-bold text-xs uppercase tracking-wider">
                  <AlertCircle className="w-4 h-4" /> Không tìm thấy trong dữ liệu đã có
                </div>
              )}
              {msg.status === 'conflicting' && (
                <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400 mb-2 font-bold text-xs uppercase tracking-wider">
                  <AlertCircle className="w-4 h-4" /> Phát hiện chứng cứ mâu thuẫn
                </div>
              )}

              {/* Enhanced Markdown Renderer */}
              {msg.role === 'assistant' ? (
                <MarkdownRenderer content={msg.text} />
              ) : (
                <div className="whitespace-pre-wrap">{msg.text}</div>
              )}

              {/* Citations Box */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t space-y-1.5" style={{ borderColor: 'var(--border-card)' }}>
                  <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--accent-teal)' }}>
                    Bằng chứng nguồn (Citations):
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.citations.map((cit, cIdx) => (
                      <button
                        key={cIdx}
                        onClick={() => handleCitationClick(cit)}
                        className="px-2.5 py-1 rounded-full text-[11px] font-semibold border flex items-center gap-1.5 transition-all hover:scale-105"
                        style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}
                      >
                        <span>{getCitationLabel(cit)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 border" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
              <Bot className="w-4 h-4" />
            </div>
            <div className="clinical-subcard rounded-2xl rounded-tl-none px-4 py-3 flex items-center gap-2 text-xs font-bold" style={{ color: 'var(--accent-teal)' }}>
              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--accent-teal-border)', borderTopColor: 'var(--accent-teal)' }} />
              <span>AI Co-pilot đang đối chiếu chứng cứ...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-3 px-4 border-t" style={{ borderColor: 'var(--border-card)', backgroundColor: 'var(--bg-card)' }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
          className="flex items-end gap-2"
        >
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
            placeholder="Nhập câu hỏi lâm sàng cho AI Co-pilot (Enter để gửi)..."
            rows={2}
            className="clinical-input flex-1 p-2.5 text-xs font-medium resize-none"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="px-4 py-2.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-40 text-white text-xs font-bold rounded-xl shadow-sm transition-all flex items-center gap-1.5 shrink-0 cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Hỏi AI</span>
          </button>
        </form>
      </div>
    </div>
  );
}
