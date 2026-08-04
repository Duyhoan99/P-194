'use client';

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { auth as authApi } from './api';

interface AuthUser {
  username: string;
  role: string;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for stored user on mount
    const stored = localStorage.getItem('clinical_user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        localStorage.removeItem('clinical_user');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await authApi.login(username, password);
    // Infer role from username pattern
    let role = 'DOCTOR';
    if (username.startsWith('admin')) role = 'ADMIN';
    else if (username.startsWith('steward')) role = 'DATA_STEWARD';
    else if (username.startsWith('compliance')) role = 'COMPLIANCE';

    const u: AuthUser = { username, role };
    setUser(u);
    localStorage.setItem('clinical_user', JSON.stringify(u));
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    }
    setUser(null);
    localStorage.removeItem('clinical_user');
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
