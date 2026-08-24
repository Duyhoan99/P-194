'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Stethoscope, Lock, User, KeyRound, ArrowRight, ShieldCheck, Sparkles } from 'lucide-react';
import Link from 'next/link';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
      router.push('/dashboard');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (user: string) => {
    setUsername(user);
    setPassword('demo');
    setError('');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden" style={{ backgroundColor: 'var(--bg-app)' }}>
      
      {/* Subtle Ambient Background */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full blur-[140px] opacity-20 pointer-events-none" style={{ backgroundColor: 'var(--accent-teal)' }} />
      </div>

      <div className="clinical-card w-full max-w-md p-8 relative z-10 space-y-7 shadow-2xl">
        
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <Link href="/" className="inline-flex items-center justify-center w-14 h-14 rounded-2xl border shadow-sm mx-auto mb-2 transition-transform hover:scale-105" style={{ backgroundColor: 'var(--accent-teal-bg)', borderColor: 'var(--accent-teal-border)', color: 'var(--accent-teal)' }}>
            <Stethoscope className="w-7 h-7" />
          </Link>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            Clinical Copilot
          </h1>
          <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
            Đăng nhập hệ thống AI hỗ trợ rà soát hồ sơ bệnh án
          </p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          
          {/* Username */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-900 dark:text-slate-200 block" htmlFor="username">
              Tên đăng nhập
            </label>
            <div className="relative">
              <User className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
              <input
                id="username"
                type="text"
                className="clinical-input w-full pl-10 pr-4 py-2.5 text-xs font-medium"
                placeholder="Nhập tên đăng nhập (VD: doctor-1)"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                autoComplete="username"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-900 dark:text-slate-200 block" htmlFor="password">
              Mật khẩu
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
              <input
                id="password"
                type="password"
                className="clinical-input w-full pl-10 pr-4 py-2.5 text-xs font-medium"
                placeholder="Nhập mật khẩu"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs font-semibold text-rose-600 dark:text-rose-300">
              ⚠️ {error}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full py-3 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white text-xs font-extrabold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer pt-3"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Đang xác thực...</span>
              </>
            ) : (
              <>
                <KeyRound className="w-4 h-4" />
                <span>Đăng nhập hệ thống</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Demo Accounts Box */}
        <div className="clinical-subcard p-4 rounded-xl space-y-2.5 border" style={{ borderColor: 'var(--border-card)' }}>
          <div className="flex items-center gap-1.5 text-xs font-bold" style={{ color: 'var(--accent-teal)' }}>
            <Sparkles className="w-3.5 h-3.5" />
            <span>Tài khoản Demo (1-Click điền nhanh)</span>
          </div>

          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => fillDemo('doctor-1')}
              className="px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all hover:scale-105 cursor-pointer"
              style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--text-primary)' }}
            >
              👨‍⚕️ doctor-1
            </button>
            <button
              type="button"
              onClick={() => fillDemo('doctor-2')}
              className="px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all hover:scale-105 cursor-pointer"
              style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--text-primary)' }}
            >
              👩‍⚕️ doctor-2
            </button>
            <button
              type="button"
              onClick={() => fillDemo('admin-1')}
              className="px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all hover:scale-105 cursor-pointer"
              style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-card)', color: 'var(--text-primary)' }}
            >
              ⚙️ admin-1
            </button>
          </div>

          <p className="text-[11px] font-medium mt-1" style={{ color: 'var(--text-muted)' }}>
            Mật khẩu mặc định: <code className="px-1.5 py-0.5 rounded font-mono font-bold" style={{ backgroundColor: 'var(--accent-teal-bg)', color: 'var(--accent-teal)' }}>demo</code>
          </p>
        </div>

        <div className="text-center pt-1">
          <Link href="/" className="text-xs font-semibold hover:underline" style={{ color: 'var(--accent-teal)' }}>
            ← Quay lại Trang giới thiệu
          </Link>
        </div>

      </div>
    </div>
  );
}
