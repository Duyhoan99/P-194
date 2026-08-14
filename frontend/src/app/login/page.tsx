'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

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
      router.push('/patients');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Đăng nhập thất bại';
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
    <div className="login-page">
      <div className="login-card">
        {/* Logo */}
        <div className="login-logo">
          <div className="login-logo-icon">🩺</div>
          <h1>Clinical Summary Agent</h1>
          <p>Hệ thống AI hỗ trợ tóm tắt hồ sơ lâm sàng</p>
        </div>

        {/* Login Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="input-group">
            <label className="input-label" htmlFor="username">Tên đăng nhập</label>
            <input
              id="username"
              type="text"
              className="input-field"
              placeholder="Nhập tên đăng nhập"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="password">Mật khẩu</label>
            <input
              id="password"
              type="password"
              className="input-field"
              placeholder="Nhập mật khẩu"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          {error && <div className="login-error">⚠️ {error}</div>}

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading || !username || !password}
            style={{ width: '100%' }}
          >
            {loading ? (
              <>
                <div className="spinner" style={{ width: 18, height: 18, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} />
                Đang đăng nhập...
              </>
            ) : (
              '🔐 Đăng nhập'
            )}
          </button>

          {/* Demo hints */}
          <div className="login-hint">
            <strong>💡 Tài khoản Demo</strong>
            <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => fillDemo('doctor-1')}
                style={{ fontSize: 12 }}
              >
                👨‍⚕️ doctor-1
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => fillDemo('doctor-2')}
                style={{ fontSize: 12 }}
              >
                👩‍⚕️ doctor-2
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => fillDemo('admin-1')}
                style={{ fontSize: 12 }}
              >
                ⚙️ admin-1
              </button>
            </div>
            <p style={{ marginTop: 8, opacity: 0.8 }}>Mật khẩu mặc định: <code style={{ background: '#e6f5f3', padding: '1px 6px', borderRadius: 4 }}>demo</code></p>
          </div>
        </form>
      </div>
    </div>
  );
}
