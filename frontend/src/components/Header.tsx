'use client';

import Link from 'next/link';

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface HeaderProps {
  title: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: React.ReactNode;
}

export default function Header({ title, breadcrumbs, actions }: HeaderProps) {
  return (
    <header className="header">
      <div>
        <h1 className="header-title">{title}</h1>
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav className="header-breadcrumb" style={{ marginTop: 2 }}>
            {breadcrumbs.map((item, i) => (
              <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {i > 0 && <span style={{ color: '#ccc' }}>/</span>}
                {item.href ? (
                  <Link href={item.href}>{item.label}</Link>
                ) : (
                  <span>{item.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </header>
  );
}
