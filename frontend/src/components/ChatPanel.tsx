'use client';

import { useState } from 'react';
import { patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { Send, Bot, User, Search, AlertCircle, XCircle } from 'lucide-react';
import { motion } from 'framer-motion';

export default function ChatPanel({ patientId }: { patientId: string }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<{role: 'user' | 'assistant', text: string, status?: string, citations?: any[]}[]>([]);
  const { setFocusedCitation } = useAppStore();

  const handleAsk = async () => {
    if (!query.trim() || loading) return;

    const userQuery = query.trim();
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
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: err.detail || 'An error occurred while communicating with Copilot.',
        status: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleCitationClick = (citation: any) => {
    setFocusedCitation(citation);
  };

  return (
    <div className="glass-panel overflow-hidden flex flex-col h-full min-h-[500px]">
      <div className="glass-header p-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-teal-500/10 flex items-center justify-center border border-teal-500/20 shadow-[0_0_15px_rgba(20,184,166,0.15)]">
          <Bot className="w-4 h-4 text-teal-400" />
        </div>
        <h3 className="text-sm font-bold tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-300">AI Co-pilot</h3>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4">
            <div className="w-20 h-20 rounded-full bg-slate-800/30 flex items-center justify-center border border-slate-700/30 shadow-inner shadow-teal-500/5">
              <Search className="w-8 h-8 text-teal-500/40" />
            </div>
            <p className="text-sm text-center font-medium text-slate-400">Ask any question about the patient's records.<br/>I will only answer based on verified evidence.</p>
            <div className="flex flex-wrap gap-2 justify-center mt-6 max-w-sm">
                <button onClick={() => setQuery('HbA1c gần đây thay đổi thế nào?')} className="px-4 py-2 bg-slate-800/30 hover:bg-teal-900/40 border border-slate-700/50 hover:border-teal-500/30 rounded-full text-xs font-medium text-slate-300 hover:text-teal-300 hover:shadow-[0_0_15px_rgba(20,184,166,0.15)] backdrop-blur-md transition-all duration-300">HbA1c gần đây thay đổi thế nào?</button>
                <button onClick={() => setQuery('Có xung đột nào trong danh sách thuốc?')} className="px-4 py-2 bg-slate-800/30 hover:bg-teal-900/40 border border-slate-700/50 hover:border-teal-500/30 rounded-full text-xs font-medium text-slate-300 hover:text-teal-300 hover:shadow-[0_0_15px_rgba(20,184,166,0.15)] backdrop-blur-md transition-all duration-300">Có xung đột nào trong danh sách thuốc?</button>
                <button onClick={() => setQuery('So sánh cận lâm sàng hôm nay với 6 tháng trước')} className="px-4 py-2 bg-slate-800/30 hover:bg-teal-900/40 border border-slate-700/50 hover:border-teal-500/30 rounded-full text-xs font-medium text-slate-300 hover:text-teal-300 hover:shadow-[0_0_15px_rgba(20,184,166,0.15)] backdrop-blur-md transition-all duration-300 flex items-center gap-1">⚡ Quick Action: So sánh cận lâm sàng</button>
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
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === 'user' 
                ? 'bg-cyan-600 text-white rounded-tr-none' 
                : 'bg-slate-800 text-slate-200 rounded-tl-none border border-slate-700'
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

              <div className="whitespace-pre-wrap">{msg.text}</div>
              
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-700 flex flex-wrap gap-2">
                  {msg.citations.map((cit: any) => (
                    <button 
                      key={cit.citation_id}
                      onClick={() => handleCitationClick(cit)}
                      className="inline-flex items-center gap-1.5 px-2 py-1 bg-slate-900 hover:bg-slate-950 text-cyan-400 text-xs font-mono rounded-md border border-slate-700 hover:border-cyan-500 transition-colors shadow-sm"
                    >
                      {cit.source_type === 'pdf' ? '📄' : '🗃️'} {cit.citation_id.split('-').pop()?.substring(0, 4)}
                    </button>
                  ))}
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

      <div className="p-4 border-t border-white/5 bg-slate-900/60 backdrop-blur-md">
        <div className="flex gap-2">
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            placeholder="Ask AI Copilot..."
            disabled={loading}
            className="flex-1 bg-slate-800/50 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500/50 border border-white/5 disabled:opacity-50 placeholder-slate-500"
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
