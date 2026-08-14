'use client';
import { HelpCircle, Book, MessageSquare, Phone, ExternalLink, Search, Mail } from 'lucide-react';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';

export default function HelpPage() {
  const { t } = useLanguage();
  return (
    <div className="page-content space-y-8 flex-1 h-full overflow-y-auto">
      {/* Page Header */}
      <div className="flex flex-col items-center justify-center border-b border-white/5 pb-10 pt-8">
        <div className="w-16 h-16 rounded-2xl bg-teal-500/20 flex items-center justify-center border border-teal-500/30 shadow-[0_0_30px_rgba(20,184,166,0.2)] mb-6">
          <HelpCircle className="w-8 h-8 text-teal-400" />
        </div>
        <h1 className="text-4xl font-bold text-slate-100 tracking-wide text-center">{t('help.title')}</h1>
        <p className="text-slate-400 mt-3 text-center max-w-lg">{t('help.subtitle')}</p>
        
        <div className="relative w-full max-w-2xl mt-8">
          <Search className="w-5 h-5 text-slate-500 absolute left-4 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder={t('help.search')} 
            className="w-full bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-2xl pl-12 pr-4 py-4 text-slate-200 focus:outline-none focus:border-teal-500/50 shadow-2xl transition-colors"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
        <SupportCard 
          icon={Book} 
          title={t('help.docs')} 
          description={t('help.docsDesc')} 
          action={t('help.docsAction')}
          color="teal"
        />
        <SupportCard 
          icon={MessageSquare} 
          title={t('help.chat')} 
          description={t('help.chatDesc')} 
          action={t('help.chatAction')}
          color="cyan"
        />
        <SupportCard 
          icon={Mail} 
          title={t('help.email')} 
          description={t('help.emailDesc')} 
          action={t('help.emailAction')}
          color="purple"
        />
      </div>

      <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl p-8 mt-12">
        <h2 className="text-xl font-bold text-slate-200 mb-6">{t('help.faq')}</h2>
        <div className="space-y-4">
          <FaqItem 
            question="How do I upload a new patient record?" 
            answer="Navigate to the 'Case Files' section or use the Dashboard. Click on the 'Upload' button and select your PDF or JSON file. The system will automatically extract and process the information."
          />
          <FaqItem 
            question="What is the Clinical Review Copilot?" 
            answer="The Clinical Review Copilot is an AI assistant that analyzes patient data against specific clinical profiles (like Type 2 Diabetes) to generate comprehensive medical summaries and highlight missing or conflicting information."
          />
          <FaqItem 
            question="Is my patient data secure and HIPAA compliant?" 
            answer="Yes, all data is encrypted both in transit and at rest. The system implements strict access controls and audit logging to ensure full compliance with healthcare data regulations."
          />
          <FaqItem 
            question="How do I reset my password?" 
            answer="If you are unable to login, click the 'Forgot Password' link on the login page. If you are already logged in, navigate to Settings > Security to update your credentials."
          />
        </div>
      </div>
    </div>
  );
}

function SupportCard({ icon: Icon, title, description, action, color }: any) {
  const colorStyles: any = {
    teal: 'text-teal-400 bg-teal-500/10 border-teal-500/20 group-hover:bg-teal-500/20',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20 group-hover:bg-cyan-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20 group-hover:bg-purple-500/20',
  };

  return (
    <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl p-6 shadow-xl flex flex-col group transition-all hover:-translate-y-1 hover:shadow-2xl hover:border-white/10">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-colors ${colorStyles[color]}`}>
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-lg font-bold text-slate-200 mb-2">{title}</h3>
      <p className="text-slate-400 text-sm mb-6 flex-1">{description}</p>
      <button className="flex items-center gap-2 text-sm font-semibold text-slate-300 group-hover:text-white transition-colors mt-auto">
        {action} <ExternalLink className="w-4 h-4" />
      </button>
    </div>
  );
}

function FaqItem({ question, answer }: { question: string, answer: string }) {
  return (
    <div className="border border-white/5 rounded-xl p-5 bg-slate-800/20 hover:bg-slate-800/40 transition-colors cursor-pointer">
      <h4 className="text-base font-semibold text-slate-200 mb-2 flex justify-between items-center">
        {question}
      </h4>
      <p className="text-sm text-slate-400 leading-relaxed">
        {answer}
      </p>
    </div>
  );
}
