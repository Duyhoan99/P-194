'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { clinical, type AssignedPatientsResponse, type ClinicalResponse } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';

interface PatientInfo {
  subjectId: number;
  overview?: ClinicalResponse;
  loading: boolean;
}

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [patients, setPatients] = useState<PatientInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;

    const loadPatients = async () => {
      setLoading(true);
      setError('');
      try {
        const resp: AssignedPatientsResponse = await clinical.getAssignedPatients();
        const patientInfos: PatientInfo[] = resp.patients.map((id) => ({
          subjectId: id,
          loading: true,
        }));
        setPatients(patientInfos);

        // Load overview for each patient in parallel
        const overviews = await Promise.allSettled(
          resp.patients.map((id) => clinical.getPatientOverview(id))
        );

        setPatients((prev) =>
          prev.map((p, i) => ({
            ...p,
            overview: overviews[i].status === 'fulfilled' ? overviews[i].value : undefined,
            loading: false,
          }))
        );
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Không thể tải danh sách bệnh nhân');
      } finally {
        setLoading(false);
      }
    };

    loadPatients();
  }, [user]);

  if (authLoading || !user) {
    return (
      <div className="loading-page" style={{ minHeight: '100vh' }}>
        <div className="spinner" />
      </div>
    );
  }

  const getPatientName = (overview?: ClinicalResponse) => {
    if (!overview?.records?.length) return null;
    const rec = overview.records.find(r => r.record_type === 'patient_demographics' || r.record_type === 'admission_overview');
    if (!rec) return null;
    return rec.data;
  };

  const getAdmissionsCount = (overview?: ClinicalResponse) => {
    if (!overview?.records) return 0;
    return overview.records.filter(r =>
      r.record_type === 'admission_overview' ||
      r.record_type === 'admission' ||
      r.data?.hadm_id
    ).length;
  };

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <Header
          title="🏥 Bảng Điều Khiển"
          actions={
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span className="badge badge-teal">👤 {user.username}</span>
              <span className="badge badge-success">{user.role}</span>
            </div>
          }
        />

        <div className="page-content">
          {/* Stats */}
          <div className="stat-grid animate-fade-in">
            <div className="stat-card">
              <div className="stat-icon teal">👥</div>
              <div>
                <div className="stat-value">{patients.length}</div>
                <div className="stat-label">Bệnh nhân được phân công</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon emerald">📋</div>
              <div>
                <div className="stat-value">{patients.reduce((sum, p) => sum + getAdmissionsCount(p.overview), 0)}</div>
                <div className="stat-label">Tổng số nhập viện</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon blue">🤖</div>
              <div>
                <div className="stat-value">AI</div>
                <div className="stat-label">Agent sẵn sàng</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon amber">📊</div>
              <div>
                <div className="stat-value">MIMIC-IV</div>
                <div className="stat-label">Nguồn dữ liệu</div>
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="login-error" style={{ marginBottom: 20 }}>
              ⚠️ {error}
            </div>
          )}

          {/* Patient List */}
          <div className="card">
            <div className="card-header">
              <h2>📋 Bệnh nhân được phân công</h2>
              <button className="btn btn-secondary btn-sm" onClick={() => window.location.reload()}>
                🔄 Làm mới
              </button>
            </div>
            <div className="card-body">
              {loading ? (
                <div className="loading-page">
                  <div className="spinner" />
                  <span>Đang tải danh sách bệnh nhân...</span>
                </div>
              ) : patients.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">📭</div>
                  <h3>Chưa có bệnh nhân nào</h3>
                  <p>Vui lòng liên hệ quản trị viên để được phân công bệnh nhân.</p>
                </div>
              ) : (
                <div className="patient-grid stagger">
                  {patients.map((patient) => {
                    const info = getPatientName(patient.overview);
                    return (
                      <div
                        key={patient.subjectId}
                        className="patient-card"
                        onClick={() => router.push(`/patients/${patient.subjectId}`)}
                      >
                        <div className="patient-card-header">
                          <span className="patient-id">
                            🏷️ Subject #{patient.subjectId}
                          </span>
                          {patient.loading ? (
                            <div className="spinner" style={{ width: 16, height: 16 }} />
                          ) : (
                            <span className="badge badge-teal">
                              {getAdmissionsCount(patient.overview)} lần nhập viện
                            </span>
                          )}
                        </div>
                        <div className="patient-card-meta">
                          {info && (
                            <>
                              {info.gender && (
                                <div className="patient-meta-item">
                                  <span className="patient-meta-icon">
                                    {info.gender === 'M' ? '👨' : '👩'}
                                  </span>
                                  Giới tính: {info.gender === 'M' ? 'Nam' : 'Nữ'}
                                </div>
                              )}
                              {info.anchor_age && (
                                <div className="patient-meta-item">
                                  <span className="patient-meta-icon">🎂</span>
                                  Tuổi tham chiếu: {String(info.anchor_age)}
                                </div>
                              )}
                            </>
                          )}
                          <div className="patient-meta-item">
                            <span className="patient-meta-icon">📊</span>
                            {patient.overview?.status === 'SUCCESS' ? 'Dữ liệu đầy đủ' :
                             patient.overview?.status === 'PARTIAL' ? 'Dữ liệu một phần' :
                             'Đang tải...'}
                          </div>
                        </div>
                        {patient.overview?.warnings && patient.overview.warnings.length > 0 && (
                          <div style={{ marginTop: 10 }}>
                            {patient.overview.warnings.slice(0, 2).map((w, i) => (
                              <div key={i} style={{ fontSize: 12, color: '#92400e', background: '#fef3c7', padding: '4px 8px', borderRadius: 4, marginTop: 4 }}>
                                ⚠️ {w}
                              </div>
                            ))}
                          </div>
                        )}
                        <div style={{ marginTop: 14, display: 'flex', gap: 8 }}>
                          <button className="btn btn-primary btn-sm" style={{ flex: 1 }}>
                            📄 Xem hồ sơ
                          </button>
                          <button
                            className="btn btn-success btn-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              router.push(`/patients/${patient.subjectId}?tab=summary`);
                            }}
                          >
                            🤖 Tóm tắt
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
