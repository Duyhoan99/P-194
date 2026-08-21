'use client';

import React, { useState, useRef, useEffect } from 'react';
import { patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { Send, Bot, User, Search, AlertCircle, XCircle, Trash2 } from 'lucide-react';
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
        return <strong key={idx} className="font-bold text-slate-100">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={idx} className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700/80 text-teal-300 font-mono text-[11px]">
            {part.slice(1, -1)}
          </code>
        );
      }
      return <React.Fragment key={idx}>{part}</React.Fragment>;
    });
  };

  return (
    <div className="space-y-2 text-xs leading-relaxed text-slate-200">
      {blocks.map((block, bIdx) => {
        if (block.type === 'table') {
          const rows = block.lines
            .map(l => l.trim().split('|').slice(1, -1).map(c => c.trim()))
            .filter(r => r.length > 0);

          if (rows.length < 2) return null;

          const headerRow = rows[0];
          const dataRows = rows.slice(2); // Skip separator row (e.g. |---|---|)

          return (
            <div key={bIdx} className="overflow-x-auto my-3 rounded-xl border border-slate-700/80 bg-slate-950/70 shadow-lg shadow-black/40">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="bg-slate-800/90 text-teal-300 border-b border-slate-700">
                    {headerRow.map((cell, cIdx) => (
                      <th key={cIdx} className="px-3 py-2.5 font-bold uppercase tracking-wider text-[11px] whitespace-nowrap">
                        {renderInline(cell)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {dataRows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className={`transition-colors hover:bg-teal-950/20 ${rIdx % 2 === 0 ? 'bg-transparent' : 'bg-slate-900/40'}`}
                    >
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3 py-2 text-slate-200 whitespace-normal">
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
                  <h4 key={lIdx} className="font-bold text-sm text-teal-300 mt-2 mb-1 flex items-center gap-1.5">
                    {renderInline(trimmed.replace('### ', ''))}
                  </h4>
                );
              }

              if (trimmed.startsWith('## ')) {
                return (
                  <h3 key={lIdx} className="font-bold text-base text-teal-200 mt-2 mb-1 flex items-center gap-1.5">
                    {renderInline(trimmed.replace('## ', ''))}
                  </h3>
                );
              }

              if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                return (
                  <div key={lIdx} className="flex items-start gap-2 pl-1 my-0.5">
                    <span className="text-teal-400 mt-0.5 font-bold">•</span>
                    <span className="flex-1">{renderInline(trimmed.slice(2))}</span>
                  </div>
                );
              }

              return (
                <p key={lIdx} className="my-0.5">
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

      const traceId = err.trace_id || (typeof detail === 'object' ? detail?.trace_id : undefined) || 'N/A';
      const code = typeof detail === 'object' ? detail?.code : undefined;

      console.warn(
        `AGENT_UNAVAILABLE\n` +
        `trace_id=${traceId}\n` +
        `patient_id=${patientId}\n` +
        `request_id=${err.request_id || 'N/A'}\n` +
        `exception=${typeof detail === 'object' ? JSON.stringify(detail) : String(detail)}`
      );

      let textToDisplay = '⚠️ Không thể truy xuất dữ liệu lúc này.\nVui lòng thử lại sau.';
      if (code === 'AGENT_UNAVAILABLE' || (typeof detail === 'string' && detail.includes('AGENT_UNAVAILABLE'))) {
        textToDisplay = '⚠️ Không thể truy xuất dữ liệu lúc này.\nVui lòng thử lại sau.';
      } else if (typeof detail === 'object' && detail?.message) {
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
    <div className="glass-panel overflow-hidden flex flex-col h-full min-h-0 shadow-2xl rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur-xl">
      {/* Header */}
      <div className="p-3 px-4 flex items-center justify-between shrink-0 border-b border-white/10 bg-slate-900/90">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-teal-500/10 flex items-center justify-center border border-teal-500/30 shadow-[0_0_15px_rgba(20,184,166,0.15)]">
            <Bot className="w-4 h-4 text-teal-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-300">
              AI Co-pilot Lâm sàng
            </h3>
            <p className="text-[10px] text-slate-400 font-mono">Grounded Clinical Reasoning</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Clear messages */}
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="p-1.5 rounded-lg bg-slate-900 hover:bg-red-950/40 border border-slate-800 hover:border-red-500/30 text-slate-400 hover:text-red-400 transition-all text-xs"
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
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4 py-8 px-4">
            <div className="w-12 h-12 rounded-2xl bg-teal-500/10 flex items-center justify-center border border-teal-500/20 shadow-inner">
              <Bot className="w-6 h-6 text-teal-400" />
            </div>
            <div className="text-center space-y-1">
              <h4 className="text-sm font-semibold text-slate-200">Trợ lý Hỏi - Đáp Lâm sàng</h4>
              <p className="text-xs text-slate-400 max-w-sm leading-relaxed">
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
                  className="text-left p-2.5 rounded-xl bg-slate-900/80 hover:bg-teal-950/40 border border-slate-800 hover:border-teal-500/40 text-slate-300 hover:text-teal-200 transition-all text-xs group shadow-sm flex flex-col gap-0.5"
                >
                  <span className="font-semibold text-[11px] text-teal-300/90 group-hover:text-teal-300">{p.label}</span>
                  <span className="text-[11px] text-slate-400 line-clamp-1 group-hover:text-slate-300">{p.text}</span>
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
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-cyan-900 text-cyan-400' : 'bg-teal-900 text-teal-400'}`}>
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === 'user'
                ? 'bg-cyan-600 text-white rounded-tr-none'
                : 'bg-slate-800/95 text-slate-200 rounded-tl-none border border-slate-700/80 shadow-md'
              }`}>

              {msg.status === 'not_found' && (
                <div className="flex items-center gap-2 text-slate-400 mb-2 font-medium text-xs uppercase tracking-wider">
                  <AlertCircle className="w-4 h-4" /> Not found in provided data
                </div>
              )}
              {msg.status === 'conflicting' && (
                <div className="flex items-center gap-2 text-amber-400 mb-2 font-medium text-xs uppercase tracking-wider">
                  <AlertCircle className="w-4 h-4" /> Conflicting evidence found
                </div>
              )}
              {msg.status === 'not_allowed' && (
                <div className="flex items-center gap-2 text-red-400 mb-2 font-medium text-xs uppercase tracking-wider">
                  <XCircle className="w-4 h-4" /> Outside AI Scope
                </div>
              )}

              {/* Enhanced Markdown Renderer */}
              {msg.role === 'assistant' ? (
                <MarkdownRenderer content={msg.text} />
              ) : (
                <div className="whitespace-pre-wrap">{msg.text}</div>
              )}

              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-700/80 flex flex-wrap gap-1.5">
                  {msg.citations.slice(0, 10).map((cit: any, citIdx: number) => (
                    <button
                      key={`${cit.citation_id || cit.evidence_id || 'cit'}-${citIdx}`}
                      onClick={() => handleCitationClick(cit)}
                      className="inline-flex items-center gap-1.5 px-2 py-1 bg-slate-900 hover:bg-slate-950 text-cyan-300 text-[11px] rounded-md border border-slate-700/80 hover:border-cyan-500 transition-colors shadow-sm"
                    >
                      {getCitationLabel(cit)}
                    </button>
                  ))}
                  {msg.citations.length > 10 && (
                    <span className="text-[10px] text-slate-400 self-center px-1">
                      +{msg.citations.length - 10} nguồn khác
                    </span>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-teal-900 text-teal-400 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-tl-none px-4 py-3 flex items-center gap-2">
              <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 p-3 px-4 border-t border-white/10 bg-slate-950/80 backdrop-blur-md">
        <div className="flex items-end gap-2.5">
          <div className="flex-1 relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAsk();
                }
              }}
              rows={2}
              placeholder="Nhập câu hỏi lâm sàng cho AI Co-pilot (Enter để gửi, Shift+Enter xuống dòng)..."
              disabled={loading}
              className="w-full bg-slate-900/90 text-slate-100 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-500/60 border border-slate-700/80 disabled:opacity-50 placeholder-slate-400 text-xs sm:text-sm resize-none chat-scrollbar leading-relaxed"
            />
          </div>
          <button
            onClick={handleAsk}
            disabled={loading || !query.trim()}
            className="h-[52px] px-4 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white rounded-xl flex items-center justify-center transition-all disabled:opacity-40 shadow-lg shadow-teal-900/30 shrink-0 font-medium text-xs gap-1.5"
            title="Gửi câu hỏi"
          >
            {loading ? (
              <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></span>
            ) : (
              <>
                <Send className="w-4 h-4" />
                <span className="hidden sm:inline">Hỏi AI</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
