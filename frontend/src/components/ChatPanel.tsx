'use client';

import React, { useState } from 'react';
import { patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { Send, Bot, User, Search, AlertCircle, XCircle, Sparkles, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import DemoScenarios from './DemoScenarios';

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
  const [messages, setMessages] = useState<{role: 'user' | 'assistant', text: string, status?: string, citations?: any[]}[]>([]);
  const [showDemoBar, setShowDemoBar] = useState(true);
  const { setFocusedCitation } = useAppStore();

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
    <div className="glass-panel overflow-hidden flex flex-col h-full min-h-[500px]">
      {/* Header */}
      <div className="glass-header p-3 px-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-teal-500/10 flex items-center justify-center border border-teal-500/20 shadow-[0_0_15px_rgba(20,184,166,0.15)]">
            <Bot className="w-4 h-4 text-teal-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-300">
              AI Co-pilot
            </h3>
            <p className="text-[10px] text-slate-400">Grounded Clinical Reasoning</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Toggle Demo Scenarios */}
          <button
            onClick={() => setShowDemoBar(prev => !prev)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all duration-200 flex items-center gap-1.5 ${
              showDemoBar
                ? 'bg-teal-500/20 border-teal-500/40 text-teal-300 shadow-[0_0_10px_rgba(20,184,166,0.2)]'
                : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800'
            }`}
            title="Bật/Tắt 5 Tiêu chí Demo Case"
          >
            <Sparkles className="w-3.5 h-3.5 text-teal-400" />
            <span className="font-semibold">5 Tiêu chí Demo</span>
            {showDemoBar ? <ChevronUp className="w-3 h-3 ml-0.5" /> : <ChevronDown className="w-3 h-3 ml-0.5" />}
          </button>

          {/* Clear messages */}
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="p-1.5 rounded-lg bg-slate-800/40 hover:bg-red-950/40 border border-slate-700/50 hover:border-red-500/30 text-slate-400 hover:text-red-400 transition-all text-xs"
              title="Xóa hội thoại"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Collapsible Demo Scenarios Bar */}
      <AnimatePresence>
        {showDemoBar && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-b border-white/5 px-3 py-2.5 bg-slate-950/40"
          >
            <DemoScenarios
              currentPatientId={patientId}
              onSelectPrompt={handleAskWithText}
              isLoading={loading}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !showDemoBar && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4 py-8">
            <div className="w-16 h-16 rounded-full bg-slate-800/30 flex items-center justify-center border border-slate-700/30 shadow-inner shadow-teal-500/5">
              <Search className="w-7 h-7 text-teal-500/40" />
            </div>
            <p className="text-xs text-center font-medium text-slate-400 max-w-sm">
              Hỏi bất kỳ câu hỏi nào về hồ sơ bệnh nhân. AI chỉ trả lời dựa trên bằng chứng y khoa đã kiểm chứng.
            </p>
            <button
              onClick={() => setShowDemoBar(true)}
              className="px-3.5 py-1.5 bg-teal-900/30 hover:bg-teal-900/50 border border-teal-500/40 text-teal-300 rounded-full text-xs font-medium flex items-center gap-1.5 shadow-sm transition-all"
            >
              <Sparkles className="w-3.5 h-3.5 text-teal-400" />
              Mở 5 Tiêu chí Demo Case
            </button>
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
            <div className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === 'user' 
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
                  {msg.citations.slice(0, 10).map((cit: any) => (
                    <button 
                      key={cit.citation_id || cit.evidence_id || Math.random()}
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
      </div>

      {/* Input area */}
      <div className="p-3 px-4 border-t border-white/5 bg-slate-900/60 backdrop-blur-md">
        <div className="flex gap-2">
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            placeholder="Nhập câu hỏi hoặc chọn từ 5 Tiêu chí Demo ở trên..."
            disabled={loading}
            className="flex-1 bg-slate-800/50 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500/50 border border-white/5 disabled:opacity-50 placeholder-slate-500 text-sm"
          />
          <button 
            onClick={handleAsk}
            disabled={loading || !query.trim()}
            className="bg-teal-600 hover:bg-teal-500 text-white p-2 px-4 rounded-lg flex items-center justify-center transition-colors disabled:opacity-50 shadow-[0_0_15px_rgba(20,184,166,0.2)]"
          >
            {loading ? <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></span> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
