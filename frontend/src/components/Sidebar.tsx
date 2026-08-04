'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

const NAV_ITEMS = [
  {
    section: 'Lâm sàng',
    items: [
      { href: '/dashboard', label: 'Bảng điều khiển', icon: '🏥' },
    ],
  },
  {
    section: 'Quản trị',
    roles: ['ADMIN'],
    items: [
      { href: '/admin', label: 'Quản lý hệ thống', icon: '⚙️' },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🩺</div>
        <div>
          <div className="sidebar-logo-text">Clinical AI</div>
          <div className="sidebar-logo-sub">Summary Agent</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((section) => {
          // Hide admin section for non-admin users
          if (section.roles && !section.roles.includes(user.role)) return null;

          return (
            <div key={section.section}>
              <div className="sidebar-section-title">{section.section}</div>
              {section.items.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`sidebar-link ${pathname === item.href || pathname.startsWith(item.href + '/') ? 'active' : ''}`}
                >
                  <span className="sidebar-link-icon">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </div>
          );
        })}
      </nav>

      {/* User info */}
      <div className="sidebar-user">
        <div className="sidebar-avatar">
          {user.username.charAt(0).toUpperCase()}
        </div>
        <div className="sidebar-user-info">
          <div className="sidebar-user-name">{user.username}</div>
          <div className="sidebar-user-role">{user.role}</div>
        </div>
        <button
          className="btn-ghost"
          onClick={logout}
          style={{ padding: '6px 8px', fontSize: '12px' }}
          title="Đăng xuất"
        >
          🚪
        </button>
      </div>
    </aside>
  );
}
