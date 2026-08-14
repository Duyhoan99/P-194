'use client';

import { useAppStore } from '@/lib/store';
import { X, FileText, Activity, AlertTriangle, ShieldCheck, ExternalLink, BookOpen } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';

export default function EvidencePanel() {
  const { isEvidencePanelOpen, setEvidencePanelOpen, focusedCitation } = useAppStore();
  const [viewMode, setViewMode] = useState<'snippet' | 'document'>('snippet');

  const pdfUrl = focusedCitation?.document_id
    ? `http://localhost:8000/api/v1/documents/${focusedCitation.document_id}/raw`
    : null;

  const isPdfSource = focusedCitation?.source_type === 'pdf';
  const pageNumber = focusedCitation?.page_number;

  // Build embedded PDF URL with page navigation
  const embeddedPdfUrl = pdfUrl
    ? `${pdfUrl}#page=${pageNumber || 1}`
    : null;

  return (
    <AnimatePresence>
      {isEvidencePanelOpen && (
        <motion.aside 
          initial={{ opacity: 0, x: 20, width: 0 }}
          animate={{ opacity: 1, x: 0, width: viewMode === 'document' ? '600px' : '400px' }}
          exit={{ opacity: 0, x: 20, width: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="border-l border-white/5 bg-slate-950/95 backdrop-blur-xl flex flex-col shrink-0 shadow-2xl shadow-cyan-900/20 z-40 overflow-hidden relative h-screen sticky top-0"
        >
          {/* Header */}
          <div className="p-4 border-b border-white/5 flex items-center justify-between bg-slate-900/60">
            <h2 className="font-semibold text-sm text-slate-200 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-cyan-400 drop-shadow-[0_0_5px_rgba(34,211,238,0.5)]" />
              Evidence Source
            </h2>
            <div className="flex items-center gap-2">
              {/* View Mode Toggle */}
              {isPdfSource && pdfUrl && (
                <div className="flex rounded-lg overflow-hidden border border-white/10">
                  <button
                    onClick={() => setViewMode('snippet')}
                    className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider transition-all ${
                      viewMode === 'snippet'
                        ? 'bg-cyan-900/50 text-cyan-300'
                        : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                    }`}
                  >
                    Snippet
                  </button>
                  <button
                    onClick={() => setViewMode('document')}
                    className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider transition-all ${
                      viewMode === 'document'
                        ? 'bg-cyan-900/50 text-cyan-300'
                        : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                    }`}
                  >
                    Document
                  </button>
                </div>
              )}
              <button 
                onClick={() => { setEvidencePanelOpen(false); setViewMode('snippet'); }}
                className="p-1.5 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-hidden flex flex-col">
            {focusedCitation ? (
              <>
                {/* Source type badge */}
                <div className="px-5 pt-4 pb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-500">
                    {focusedCitation.source_type === 'pdf' ? <FileText className="w-3.5 h-3.5 text-cyan-400" /> : <Activity className="w-3.5 h-3.5 text-teal-400" />}
                    <span>{focusedCitation.source_type}</span>
                  </div>
                  {isPdfSource && pdfUrl && (
                    <a
                      href={pdfUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300 uppercase tracking-widest font-bold transition-colors"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Open Full
                    </a>
                  )}
                </div>

                {/* Document name */}
                <div className="px-5 pb-3">
                  <h3 className="text-base font-semibold text-slate-100 leading-tight">
                    {focusedCitation.document_name || focusedCitation.resource_type || focusedCitation.source_record_id || 'Source Document'}
                  </h3>
                  {pageNumber && (
                    <p className="text-sm text-cyan-400 font-medium mt-1 flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5" />
                      Page {pageNumber}
                    </p>
                  )}
                </div>

                {/* OCR Warning */}
                {focusedCitation.ocr_confidence && focusedCitation.ocr_confidence < 0.8 && (
                  <div className="mx-5 mb-3 flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>Low OCR confidence ({(focusedCitation.ocr_confidence * 100).toFixed(0)}%). Please verify original document.</span>
                  </div>
                )}

                {/* Content Area */}
                <div className="flex-1 overflow-hidden">
                  {viewMode === 'document' && isPdfSource && embeddedPdfUrl ? (
                    /* ===== PDF VIEWER MODE (Like NotebookLM) ===== */
                    <div className="h-full flex flex-col">
                      {/* Highlighted snippet banner at top */}
                      <div className="mx-4 mb-2 p-3 rounded-lg bg-cyan-900/20 border border-cyan-500/20">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-cyan-500 mb-1.5 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.8)] animate-pulse" />
                          Referenced Text
                        </div>
                        <p className="text-sm text-cyan-200 font-medium leading-relaxed">
                          &ldquo;{focusedCitation.snippet}&rdquo;
                        </p>
                      </div>
                      
                      {/* Embedded PDF */}
                      <div className="flex-1 mx-4 mb-4 rounded-xl overflow-hidden border border-white/10 bg-white">
                        <iframe 
                          src={embeddedPdfUrl}
                          className="w-full h-full"
                          title="PDF Document Viewer"
                        />
                      </div>
                    </div>
                  ) : (
                    /* ===== SNIPPET MODE ===== */
                    <div className="px-5 pb-5 overflow-y-auto h-full space-y-5">
                      {/* Snippet Box */}
                      <div>
                        <h4 className="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-widest flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.8)]" />
                          Source Text
                        </h4>
                        <div className="p-4 rounded-xl bg-slate-900/60 border border-white/5 text-sm text-slate-200 leading-relaxed relative group">
                          <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-teal-500/5 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity" />
                          <span className="relative z-10 font-medium">&ldquo;{focusedCitation.snippet}&rdquo;</span>
                        </div>
                      </div>

                      {/* Open Document Button (for PDF sources) */}
                      {isPdfSource && pdfUrl && (
                        <button
                          onClick={() => setViewMode('document')}
                          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-cyan-900/20 border border-cyan-500/20 text-cyan-400 hover:bg-cyan-900/30 hover:text-cyan-300 transition-all text-sm font-semibold"
                        >
                          <FileText className="w-4 h-4" />
                          View Original Document
                        </button>
                      )}

                      {/* Metadata */}
                      <div className="pt-4 border-t border-white/5">
                        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
                          {focusedCitation.citation_id && (
                            <>
                              <dt className="text-slate-500">Citation ID</dt>
                              <dd className="text-slate-300 font-mono truncate" title={focusedCitation.citation_id}>{focusedCitation.citation_id}</dd>
                            </>
                          )}
                          {focusedCitation.document_id && (
                            <>
                              <dt className="text-slate-500">Document ID</dt>
                              <dd className="text-slate-300 font-mono truncate" title={focusedCitation.document_id}>{focusedCitation.document_id}</dd>
                            </>
                          )}
                          {focusedCitation.resource_id && (
                            <>
                              <dt className="text-slate-500">Resource ID</dt>
                              <dd className="text-slate-300 font-mono truncate" title={focusedCitation.resource_id}>{focusedCitation.resource_id}</dd>
                            </>
                          )}
                          {focusedCitation.source_checksum && (
                            <>
                              <dt className="text-slate-500">Checksum</dt>
                              <dd className="text-slate-300 font-mono truncate" title={focusedCitation.source_checksum}>{focusedCitation.source_checksum.substring(0, 16)}...</dd>
                            </>
                          )}
                        </dl>
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center text-slate-500 p-8">
                <ShieldCheck className="w-12 h-12 mb-3 opacity-20" />
                <p className="text-sm">Select a citation chip in the review<br/>or chat to view source evidence.</p>
              </div>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
