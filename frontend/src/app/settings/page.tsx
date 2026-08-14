'use client';
import { useState } from 'react';
import { Settings, User, Bell, Shield, Database, ChevronRight, Check } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';
import { useAuth } from '@/lib/auth';
import { useAppStore } from '@/lib/store';

export default function SettingsPage() {
  const { t, language, setLanguage } = useLanguage();
  const { user } = useAuth();
  
  const { darkMode, setDarkMode, compactView, setCompactView } = useAppStore();

  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 3000);
    }, 800);
  };

  return (
    <div className="page-content space-y-8 flex-1 h-full overflow-y-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-6 transition-all">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/20 flex items-center justify-center border border-cyan-500/30 shadow-[0_0_20px_rgba(34,211,238,0.2)]">
            <Settings className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-100 tracking-wide">{t('set.title')}</h1>
            <p className="text-slate-400 text-sm mt-1">{t('set.subtitle')}</p>
          </div>
        </div>
        <button 
          onClick={handleSave}
          disabled={isSaving || isSaved}
          className={`flex items-center gap-2 font-semibold py-2 px-6 rounded-xl transition-all shadow-[0_0_15px_rgba(34,211,238,0.3)] ${
            isSaved 
              ? 'bg-emerald-500 text-slate-900 shadow-[0_0_15px_rgba(16,185,129,0.3)]' 
              : isSaving
              ? 'bg-cyan-500/50 text-slate-900 cursor-not-allowed'
              : 'bg-cyan-500 hover:bg-cyan-400 text-slate-900'
          }`}
        >
          {isSaving ? (
            <div className="w-4 h-4 border-2 border-slate-900 border-t-transparent rounded-full animate-spin"></div>
          ) : isSaved ? (
            <Check className="w-4 h-4" />
          ) : null}
          {isSaved ? 'Saved!' : isSaving ? 'Saving...' : t('set.save')}
        </button>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar Navigation */}
        <div className="w-full lg:w-64 flex flex-col gap-2">
          <SettingNav active icon={User} label={t('set.nav.profile')} />
          <SettingNav icon={Bell} label={t('set.nav.notify')} />
          <SettingNav icon={Shield} label={t('set.nav.security')} />
          <SettingNav icon={Database} label={t('set.nav.ai')} />
        </div>

        {/* Settings Content */}
        <div className="flex-1 space-y-6">
          <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl p-6 transition-all">
            <h2 className="text-lg font-bold text-slate-200 mb-6">{t('set.personal')}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm text-slate-400 mb-2">{t('set.fullName')}</label>
                <input 
                  type="text" 
                  defaultValue={user?.username || 'Unknown'}
                  className="w-full bg-slate-800/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-2">{t('set.email')}</label>
                <input 
                  type="email" 
                  defaultValue={user ? `${user.username}@hospital.org` : ''}
                  className="w-full bg-slate-800/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-2">{t('set.role')}</label>
                <input 
                  type="text" 
                  readOnly
                  value={user?.role || 'DOCTOR'}
                  className="w-full bg-slate-800/50 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-400 focus:outline-none opacity-80 cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl p-6 transition-all">
            <h2 className="text-lg font-bold text-slate-200 mb-6">{t('set.systemPref')}</h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between py-3 border-b border-white/5">
                <div>
                  <h3 className="text-sm font-medium text-slate-200">{t('set.lang')}</h3>
                  <p className="text-xs text-slate-400 mt-1">{t('set.langDesc')}</p>
                </div>
                <div className="flex bg-slate-800 rounded-lg p-1 border border-white/10">
                  <button 
                    onClick={() => setLanguage('en')}
                    className={`px-3 py-1 text-sm rounded-md transition-colors ${language === 'en' ? 'bg-cyan-500 text-slate-900 font-semibold shadow-sm' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    English
                  </button>
                  <button 
                    onClick={() => setLanguage('vi')}
                    className={`px-3 py-1 text-sm rounded-md transition-colors ${language === 'vi' ? 'bg-cyan-500 text-slate-900 font-semibold shadow-sm' : 'text-slate-400 hover:text-slate-200'}`}
                  >
                    Tiếng Việt
                  </button>
                </div>
              </div>

              <ToggleRow 
                title={t('set.darkMode')} 
                description={t('set.darkModeDesc')} 
                active={darkMode} 
                onChange={() => setDarkMode(!darkMode)}
              />
              <ToggleRow 
                title={t('set.compact')} 
                description={t('set.compactDesc')} 
                active={compactView} 
                onChange={() => setCompactView(!compactView)}
              />
            </div>
          </div>
          
          <div className="bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl p-6 border-red-500/20 transition-all">
            <h2 className="text-lg font-bold text-red-400 mb-2">{t('set.danger')}</h2>
            <p className="text-sm text-slate-400 mb-4">{t('set.dangerDesc')}</p>
            <button className="border border-red-500/50 text-red-400 hover:bg-red-500/10 font-medium py-2 px-4 rounded-xl transition-colors">
              {t('set.deleteAcc')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingNav({ icon: Icon, label, active = false }: any) {
  return (
    <button className={`w-full flex items-center justify-between p-3 rounded-xl transition-all ${
      active 
        ? 'bg-cyan-500/10 border border-cyan-500/20 text-cyan-400' 
        : 'bg-transparent border border-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
    }`}>
      <div className="flex items-center gap-3">
        <Icon className="w-5 h-5" />
        <span className="font-medium text-sm">{label}</span>
      </div>
      <ChevronRight className={`w-4 h-4 ${active ? 'opacity-100' : 'opacity-0 -translate-x-2'}`} />
    </button>
  );
}

function ToggleRow({ title, description, active, onChange }: { title: string, description: string, active: boolean, onChange: () => void }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-white/5 last:border-0 last:pb-0">
      <div>
        <h3 className="text-sm font-medium text-slate-200">{title}</h3>
        <p className="text-xs text-slate-400 mt-1">{description}</p>
      </div>
      <div 
        onClick={onChange}
        className={`w-12 h-6 rounded-full p-1 cursor-pointer transition-colors ${active ? 'bg-cyan-500' : 'bg-slate-700'}`}
      >
        <div className={`w-4 h-4 rounded-full bg-white transition-transform shadow-sm ${active ? 'translate-x-6' : 'translate-x-0'}`}></div>
      </div>
    </div>
  );
}
