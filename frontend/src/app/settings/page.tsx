'use client';

import { useState } from 'react';
import { Settings, User, Shield, Check, Save, Clock } from 'lucide-react';
import { useLanguage } from '@/lib/i18n';
import { useAuth } from '@/lib/auth';
import { useAppStore } from '@/lib/store';

export default function SettingsPage() {
  const { t, language, setLanguage } = useLanguage();
  const { user } = useAuth();
  const { 
    darkMode, setDarkMode, 
    compactView, setCompactView 
  } = useAppStore();

  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  // Profile state
  const [fullName, setFullName] = useState(user?.username || 'doctor-1');
  const [email, setEmail] = useState(user ? `${user.username}@hospital.org` : 'doctor-1@hospital.org');
  const [sessionTimeout, setSessionTimeout] = useState('30');

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 3000);
    }, 600);
  };

  return (
    <div className="page-content space-y-7 flex-1 h-full overflow-y-auto max-w-4xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b pb-5" style={{ borderColor: 'var(--border-card)' }}>
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center border shadow-sm" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
            <Settings className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">{t('set.title')}</h1>
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Cấu hình thông tin bác sĩ và tùy chọn giao diện làm việc</p>
          </div>
        </div>

        <button 
          onClick={handleSave}
          disabled={isSaving || isSaved}
          className="flex items-center gap-2 font-extrabold text-xs py-2.5 px-6 rounded-xl transition-all shadow-sm cursor-pointer bg-teal-600 hover:bg-teal-700 text-white disabled:opacity-50"
        >
          {isSaving ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Đang lưu...</span>
            </>
          ) : isSaved ? (
            <>
              <Check className="w-4 h-4" />
              <span>Đã lưu thành công!</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>{t('set.save')}</span>
            </>
          )}
        </button>
      </div>

      <div className="space-y-6">
        
        {/* 1. Personal Information */}
        <div className="clinical-card p-6 space-y-5">
          <h2 className="text-base font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <User className="w-4 h-4 text-teal-600 dark:text-teal-400" />
            <span>{t('set.personal')}</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-slate-900 dark:text-slate-100">
                {t('set.fullName')}
              </label>
              <input 
                type="text" 
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="clinical-input w-full px-4 py-2.5 text-xs font-semibold"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-slate-900 dark:text-slate-100">
                {t('set.email')}
              </label>
              <input 
                type="email" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="clinical-input w-full px-4 py-2.5 text-xs font-semibold"
              />
            </div>

            <div className="space-y-1.5 md:col-span-2">
              <label className="block text-xs font-bold text-slate-900 dark:text-slate-100">
                {t('set.role')}
              </label>
              <input 
                type="text" 
                readOnly
                value={user?.role || 'BÁC SĨ ĐIỀU TRỊ (DOCTOR)'}
                className="clinical-subcard w-full px-4 py-2.5 text-xs font-bold cursor-not-allowed opacity-80"
              />
            </div>
          </div>
        </div>

        {/* 2. System & Display Preferences */}
        <div className="clinical-card p-6 space-y-5">
          <h2 className="text-base font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Settings className="w-4 h-4 text-teal-600 dark:text-teal-400" />
            <span>Tùy chọn giao diện &amp; Trải nghiệm làm việc</span>
          </h2>

          <div className="space-y-4">
            {/* Language Switch */}
            <div className="flex items-center justify-between py-3 border-b" style={{ borderColor: 'var(--border-card)' }}>
              <div>
                <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">{t('set.lang')}</h3>
                <p className="text-[11px] font-medium mt-0.5" style={{ color: 'var(--text-muted)' }}>{t('set.langDesc')}</p>
              </div>
              <div className="flex p-1 rounded-xl border" style={{ backgroundColor: 'var(--bg-subcard)', borderColor: 'var(--border-card)' }}>
                <button 
                  onClick={() => setLanguage('en')}
                  className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                    language === 'en' 
                      ? 'bg-teal-600 text-white shadow-sm' 
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                  }`}
                >
                  English
                </button>
                <button 
                  onClick={() => setLanguage('vi')}
                  className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                    language === 'vi' 
                      ? 'bg-teal-600 text-white shadow-sm' 
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                  }`}
                >
                  Tiếng Việt
                </button>
              </div>
            </div>

            {/* Dark Mode Toggle */}
            <ToggleRow 
              title={t('set.darkMode')} 
              description="Chuyển đổi giữa chế độ Sáng y tế và chế độ Tối bảo vệ mắt." 
              active={darkMode} 
              onChange={() => setDarkMode(!darkMode)}
            />
            
            {/* Compact View Toggle */}
            <ToggleRow 
              title={t('set.compact')} 
              description="Thu nhỏ khoảng cách và kích thước thẻ để hiển thị tối đa dữ liệu trên một màn hình." 
              active={compactView} 
              onChange={() => setCompactView(!compactView)}
            />
          </div>
        </div>

        {/* 3. Security & Session */}
        <div className="clinical-card p-6 space-y-4">
          <h2 className="text-base font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Shield className="w-4 h-4 text-teal-600 dark:text-teal-400" />
            <span>Bảo mật phiên làm việc</span>
          </h2>

          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-teal-600" />
              <span>Thời gian tự động khóa phiên khi không thao tác (Session Timeout)</span>
            </label>
            <select 
              value={sessionTimeout}
              onChange={(e) => setSessionTimeout(e.target.value)}
              className="clinical-input w-full px-4 py-2.5 text-xs font-semibold"
            >
              <option value="15">15 phút không hoạt động</option>
              <option value="30">30 phút không hoạt động (Khuyến nghị phòng khám)</option>
              <option value="60">60 phút không hoạt động</option>
            </select>
          </div>
        </div>

      </div>
    </div>
  );
}

function ToggleRow({ title, description, active, onChange }: { title: string, description: string, active: boolean, onChange: () => void }) {
  return (
    <div className="flex items-center justify-between py-3 border-b" style={{ borderColor: 'var(--border-card)' }}>
      <div className="pr-4">
        <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">{title}</h3>
        <p className="text-[11px] font-medium mt-0.5" style={{ color: 'var(--text-muted)' }}>{description}</p>
      </div>
      <button 
        type="button"
        role="switch"
        aria-checked={active}
        onClick={onChange}
        className={`w-12 h-6.5 rounded-full p-0.5 transition-all duration-300 cursor-pointer shrink-0 relative flex items-center ${
          active ? 'bg-teal-600 shadow-[0_0_10px_rgba(13,148,136,0.4)]' : 'bg-slate-300 dark:bg-slate-700'
        }`}
      >
        <div className={`bg-white w-5 h-5 rounded-full shadow-md transform transition-transform duration-300 ${
          active ? 'translate-x-6' : 'translate-x-0.5'
        }`} />
      </button>
    </div>
  );
}
