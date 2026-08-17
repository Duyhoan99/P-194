'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { admin, type UserResponse, type AuditEntry } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import StatusBadge from '@/components/StatusBadge';

type AdminTab = 'users' | 'audit';

export default function AdminPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<AdminTab>('users');
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Assignment form
  const [assignUserId, setAssignUserId] = useState('');
  const [assignSubjectId, setAssignSubjectId] = useState('');
  const [assignLoading, setAssignLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
    if (!authLoading && user && user.role !== 'ADMIN') router.replace('/dashboard');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user || user.role !== 'ADMIN') return;
    loadData();
  }, [user, activeTab]);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      if (activeTab === 'users') {
        const resp = await admin.listUsers();
        setUsers(resp.users);
      } else {
        const resp = await admin.listAudit();
        setAudit(resp.events);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Lỗi tải dữ liệu');
    } finally {
      setLoading(false);
    }
  };

  const handleAssign = async () => {
    if (!assignUserId || !assignSubjectId) return;
    setAssignLoading(true);
    try {
      await admin.grantAssignment(assignUserId, Number(assignSubjectId));
      setAssignUserId('');
      setAssignSubjectId('');
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể gán bệnh nhân');
    } finally {
      setAssignLoading(false);
    }
  };

  const handleRevoke = async (userId: string, subjectId: number) => {
    try {
      await admin.revokeAssignment(userId, subjectId);
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể thu hồi phân công');
    }
  };

  if (authLoading || !user) {
    return <div className="loading-page" style={{ minHeight: '100vh' }}><div className="spinner" /></div>;
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <Header
          title="⚙️ Quản trị hệ thống"
          actions={<span className="badge badge-info">ADMIN</span>}
        />

        <div className="page-content">
          {/* Tabs */}
          <div className="tabs">
            <button className={`tab ${activeTab === 'users' ? 'active' : ''}`} onClick={() => setActiveTab('users')}>
              👥 Quản lý người dùng
            </button>
            <button className={`tab ${activeTab === 'audit' ? 'active' : ''}`} onClick={() => setActiveTab('audit')}>
              📋 Audit Log
            </button>
          </div>

          {error && <div className="login-error" style={{ marginBottom: 16 }}>⚠️ {error}</div>}

          {activeTab === 'users' ? (
            /* ========== USERS TAB ========== */
            <div className="animate-fade-in">
              {/* Assign Form */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header"><h2>➕ Phân công bệnh nhân</h2></div>
                <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
                  <div className="input-group" style={{ flex: 1 }}>
                    <label className="input-label">User ID</label>
                    <input
                      className="input-field"
                      placeholder="VD: doctor-1"
                      value={assignUserId}
                      onChange={(e) => setAssignUserId(e.target.value)}
                    />
                  </div>
                  <div className="input-group" style={{ flex: 1 }}>
                    <label className="input-label">Subject ID</label>
                    <input
                      className="input-field"
                      type="number"
                      placeholder="VD: 10000032"
                      value={assignSubjectId}
                      onChange={(e) => setAssignSubjectId(e.target.value)}
                    />
                  </div>
                  <button className="btn btn-primary" onClick={handleAssign} disabled={assignLoading}>
                    {assignLoading ? <div className="spinner" style={{ width: 16, height: 16 }} /> : '➕ Gán'}
                  </button>
                </div>
              </div>

              {/* Users Table */}
              <div className="card">
                <div className="card-header">
                  <h2>👥 Danh sách người dùng</h2>
                  <button className="btn btn-secondary btn-sm" onClick={loadData}>🔄 Làm mới</button>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                  {loading ? (
                    <div className="loading-page"><div className="spinner" /><span>Đang tải...</span></div>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>User ID</th>
                          <th>Vai trò</th>
                          <th>Trạng thái</th>
                          <th>Bệnh nhân được gán</th>
                          <th>Hành động</th>
                        </tr>
                      </thead>
                      <tbody>
                        {users.map((u) => (
                          <tr key={u.user_id}>
                            <td style={{ fontWeight: 600 }}>{u.user_id}</td>
                            <td><span className="badge badge-teal">{u.role}</span></td>
                            <td><StatusBadge status={u.state || 'ACTIVE'} size="sm" /></td>
                            <td>
                              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                {u.assignments.length === 0 ? (
                                  <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Chưa gán</span>
                                ) : (
                                  u.assignments.map((a) => (
                                    <span key={a} className="badge badge-info" style={{ fontSize: 11 }}>
                                      {a}
                                    </span>
                                  ))
                                )}
                              </div>
                            </td>
                            <td>
                              {u.role === 'DOCTOR' && u.assignments.length > 0 && (
                                <div style={{ display: 'flex', gap: 4 }}>
                                  {u.assignments.map((a) => {
                                    const sid = parseInt(a.replace('subject-', ''));
                                    return (
                                      <button
                                        key={a}
                                        className="btn btn-danger btn-sm"
                                        style={{ fontSize: 11, padding: '3px 8px' }}
                                        onClick={() => handleRevoke(u.user_id, sid)}
                                        title={`Thu hồi ${a}`}
                                      >
                                        ✕ {a.replace('subject-', '#')}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* ========== AUDIT TAB ========== */
            <div className="card animate-fade-in">
              <div className="card-header">
                <h2>📋 Nhật ký kiểm toán</h2>
                <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                  {audit.length} sự kiện
                </span>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                {loading ? (
                  <div className="loading-page"><div className="spinner" /><span>Đang tải...</span></div>
                ) : audit.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">📭</div>
                    <h3>Chưa có sự kiện nào</h3>
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Thời gian</th>
                        <th>Người thực hiện</th>
                        <th>Hành động</th>
                        <th>Đối tượng</th>
                        <th>Kết quả</th>
                        <th>Trace ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.map((entry, idx) => (
                        <tr key={idx}>
                          <td style={{ fontSize: 13, whiteSpace: 'nowrap' }}>
                            {new Date(entry.timestamp).toLocaleString('vi-VN')}
                          </td>
                          <td style={{ fontWeight: 500 }}>{entry.actor}</td>
                          <td>
                            <span className="badge badge-teal" style={{ fontSize: 11 }}>
                              {entry.action.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td>{entry.subject_reference}</td>
                          <td><StatusBadge status={entry.result} size="sm" /></td>
                          <td style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                            {entry.trace_id.slice(0, 8)}...
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
