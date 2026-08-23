'use client';

import { X, ExternalLink } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';
import { motion, AnimatePresence } from 'framer-motion';
import { useEffect } from 'react';

interface DocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string | null;
}

export default function DocumentModal({ isOpen, onClose, documentId }: DocumentModalProps) {
  const { language } = useLanguage();

  // Prevent background scrolling when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen || !documentId) return null;

  const docUrl = `${process.env.NEXT_PUBLIC_API_URL || ''}/api/v1/documents/${documentId}/raw`;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
        />
        
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-5xl h-[85vh] bg-white dark:bg-[#112240] border border-slate-700 shadow-2xl rounded-2xl flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-white dark:bg-[#112240]/50">
            <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200 truncate pr-4">
              {documentId}
            </h3>
            <div className="flex items-center gap-3">
              <a
                href={docUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-cyan-400 bg-cyan-400/10 hover:bg-cyan-400/20 rounded-lg transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
                {language === 'vi' ? 'Mở tab mới' : 'Open in new tab'}
              </a>
              <button
                onClick={onClose}
                className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 bg-slate-950 p-2 sm:p-4">
            <iframe
              src={docUrl}
              className="w-full h-full rounded-xl border border-slate-800 bg-white"
              title="Document Preview"
            />
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
