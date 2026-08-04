'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
  clinical,
  summaries,
  type ClinicalResponse,
  type ClinicalRecord,
  type SummaryVersion,
} from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import StatusBadge from '@/components/StatusBadge';

type TabKey = 'overview' | 'timeline' | 'diagnoses' | 'labs' | 'medications' | 'icu' | 'summary';

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'overview', label: 'Tổng quan', icon: '📋' },
  { key: 'timeline', label: 'Timeline', icon: '📅' },
  { key: 'diagnoses', label: 'Chẩn đoán', icon: '🩻' },
  { key: 'labs', label: 'Xét nghiệm', icon: '🧪' },
  { key: 'medications', label: 'Thuốc', icon: '💊' },
  { key: 'icu', label: 'ICU', icon: '🏥' },
  { key: 'summary', label: 'Tóm tắt AI', icon: '🤖' },
];

export default function PatientDetailPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const subjectId = Number(params.id);
  const initialTab = (searchParams.get('tab') as TabKey) || 'overview';

  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);
  const [tabData, setTabData] = useState<Record<string, ClinicalResponse | null>>({});
  const [tabLoading, setTabLoading] = useState<Record<string, boolean>>({});
  const [summaryData, setSummaryData] = useState<SummaryVersion | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState('');
  const [generating, setGenerating] = useState(false);

  // Checklist state for approval
  const [checklist, setChecklist] = useState({
    reviewed_summary: false,
    checked_critical_evidence: false,
    understands_ai_limitations: false,
    confirms_edits: false,
  });
  const [rejectReason, setRejectReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [user, authLoading, router]);

  const loadTabData = useCallback(async (tab: TabKey) => {
    if (tab === 'summary') return;
    if (tabData[tab] || tabLoading[tab]) return;

    setTabLoading(prev => ({ ...prev, [tab]: true }));
    try {
      let resp: ClinicalResponse;
      switch (tab) {
        case 'overview':
          resp = await clinical.getPatientOverview(subjectId);
          break;
        case 'timeline':
          resp = await clinical.getTimeline(subjectId);
          break;
        case 'diagnoses':
          resp = await clinical.getDiagnosesProcedures(subjectId);
          break;
        case 'labs':
          resp = await clinical.getLabs(subjectId);
          break;
        case 'medications':
          resp = await clinical.getMedications(subjectId);
          break;
        case 'icu':
          resp = await clinical.getIcuEvents(subjectId);
          break;
        default:
          return;
      }
      setTabData(prev => ({ ...prev, [tab]: resp }));
    } catch {
      setTabData(prev => ({ ...prev, [tab]: { status: 'ERROR', records: [], warnings: ['Không thể tải dữ liệu'], limitations: [], trace_id: '', page: { has_more: false } } }));
    } finally {
      setTabLoading(prev => ({ ...prev, [tab]: false }));
    }
  }, [subjectId, tabData, tabLoading]);

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError('');
    try {
      const resp = await summaries.getCurrent(subjectId);
      setSummaryData(resp);
    } catch {
      setSummaryData(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    if (!user) return;
    loadTabData(activeTab);
    if (activeTab === 'summary') loadSummary();
  }, [activeTab, user, loadTabData, loadSummary]);

  const handleGenerate = async () => {
    setGenerating(true);
    setSummaryError('');
    try {
      const resp = await summaries.generate(subjectId);
      setSummaryData(resp);
    } catch (err: unknown) {
      setSummaryError(err instanceof Error ? err.message : 'Không thể tạo tóm tắt');
    } finally {
      setGenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!summaryData) return;
    setActionLoading(true);
    try {
      const resp = await summaries.approve(summaryData.summary_id, checklist);
      setSummaryData(resp);
    } catch (err: unknown) {
      setSummaryError(err instanceof Error ? err.message : 'Không thể phê duyệt');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!summaryData || !rejectReason.trim()) return;
    setActionLoading(true);
    try {
      const resp = await summaries.reject(summaryData.summary_id, rejectReason);
      setSummaryData(resp);
      setRejectReason('');
    } catch (err: unknown) {
      setSummaryError(err instanceof Error ? err.message : 'Không thể từ chối');
    } finally {
      setActionLoading(false);
    }
  };

  const handleExport = async () => {
    if (!summaryData) return;
    try {
      const blob = await summaries.exportPdf(summaryData.summary_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `clinical-summary-${summaryData.summary_id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setSummaryError(err instanceof Error ? err.message : 'Không thể xuất PDF');
    }
  };

  if (authLoading || !user) {
    return <div className="loading-page" style={{ minHeight: '100vh' }}><div className="spinner" /></div>;
  }

  const currentData = tabData[activeTab];
  const isLoading = tabLoading[activeTab];

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <Header
          title={`Bệnh nhân #${subjectId}`}
          breadcrumbs={[
            { label: 'Bảng điều khiển', href: '/dashboard' },
            { label: `Subject #${subjectId}` },
          ]}
          actions={
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary btn-sm" onClick={() => router.push('/dashboard')}>
                ← Quay lại
              </button>
            </div>
          }
        />

        <div className="page-content">
          {/* Tabs */}
          <div className="tabs">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                className={`tab ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.icon} {tab.label}
                {tabData[tab.key] && (
                  <span className="tab-count">{tabData[tab.key]!.records.length}</span>
                )}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === 'summary' ? (
            /* ========== SUMMARY TAB ========== */
            <div className="animate-fade-in">
              {summaryLoading ? (
                <div className="loading-page"><div className="spinner" /><span>Đang tải tóm tắt...</span></div>
              ) : summaryData ? (
                <div>
                  {/* Summary Header */}
                  <div className="card" style={{ marginBottom: 20 }}>
                    <div className="card-header">
                      <div>
                        <h2>📄 Tóm tắt lâm sàng</h2>
                        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                          Phiên bản {summaryData.version_number} · {new Date(summaryData.created_at).toLocaleString('vi-VN')}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <StatusBadge status={summaryData.status} />
                        {(summaryData.status === 'APPROVED' || summaryData.status === 'EXPORTED') && (
                          <button className="btn btn-secondary btn-sm" onClick={handleExport}>
                            📥 Xuất PDF
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Summary Sections */}
                  {summaryData.draft.sections && Object.entries(summaryData.draft.sections).map(([section, claims]) => (
                    <div key={section} className="summary-section animate-slide-in">
                      <div className="summary-section-title">
                        📌 {section}
                        <span className="tab-count">{claims.length}</span>
                      </div>
                      {claims.map((claim) => (
                        <div key={claim.claim_id} className="summary-claim">
                          <span>{claim.text}</span>
                          {claim.citation_ids.length > 0 && (
                            <span style={{ marginLeft: 8 }}>
                              {claim.citation_ids.map((cid) => (
                                <span key={cid} className="citation-ref" title={`Citation: ${cid}`}>
                                  [{cid}]
                                </span>
                              ))}
                            </span>
                          )}
                          <StatusBadge status={claim.status} size="sm" />
                        </div>
                      ))}
                    </div>
                  ))}

                  {/* Conflicts */}
                  {summaryData.draft.conflicts && summaryData.draft.conflicts.length > 0 && (
                    <div style={{ marginTop: 20 }}>
                      <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12, color: '#92400e' }}>⚠️ Mâu thuẫn dữ liệu</h3>
                      {summaryData.draft.conflicts.map((c) => (
                        <div key={c.conflict_id} className="conflict-box">
                          <div className="conflict-box-title">
                            {c.topic}
                            <StatusBadge status={c.status} size="sm" />
                          </div>
                          {c.resolution_note && <p>{c.resolution_note}</p>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Limitations */}
                  {summaryData.draft.limitations && summaryData.draft.limitations.length > 0 && (
                    <div style={{ marginTop: 20 }}>
                      <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12, color: '#1e40af' }}>ℹ️ Giới hạn</h3>
                      {summaryData.draft.limitations.map((lim, i) => (
                        <div key={i} className="limitation-box"><p>{lim}</p></div>
                      ))}
                    </div>
                  )}

                  {/* Review Actions */}
                  {summaryData.status === 'DRAFT' && (
                    <div className="card" style={{ marginTop: 24 }}>
                      <div className="card-header"><h2>✅ Rà soát & Phê duyệt</h2></div>
                      <div className="card-body">
                        <div className="checklist">
                          {[
                            { key: 'reviewed_summary' as const, label: 'Tôi đã đọc toàn bộ bản tóm tắt' },
                            { key: 'checked_critical_evidence' as const, label: 'Tôi đã kiểm tra các bằng chứng quan trọng' },
                            { key: 'understands_ai_limitations' as const, label: 'Tôi hiểu giới hạn của AI và bản tóm tắt này' },
                            { key: 'confirms_edits' as const, label: 'Tôi xác nhận các chỉnh sửa (nếu có) là chính xác' },
                          ].map(item => (
                            <div
                              key={item.key}
                              className={`checklist-item ${checklist[item.key] ? 'checked' : ''}`}
                              onClick={() => setChecklist(prev => ({ ...prev, [item.key]: !prev[item.key] }))}
                            >
                              <div className="checklist-checkbox">
                                {checklist[item.key] && '✓'}
                              </div>
                              <span className="checklist-text">{item.label}</span>
                            </div>
                          ))}
                        </div>
                        <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
                          <button
                            className="btn btn-success"
                            disabled={!Object.values(checklist).every(Boolean) || actionLoading}
                            onClick={handleApprove}
                          >
                            {actionLoading ? <div className="spinner" style={{ width: 16, height: 16 }} /> : '✅ Phê duyệt'}
                          </button>
                          <div style={{ flex: 1, display: 'flex', gap: 8 }}>
                            <input
                              className="input-field"
                              placeholder="Lý do từ chối..."
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                              style={{ flex: 1 }}
                            />
                            <button
                              className="btn btn-danger"
                              disabled={!rejectReason.trim() || actionLoading}
                              onClick={handleReject}
                            >
                              ❌ Từ chối
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {summaryError && (
                    <div className="login-error" style={{ marginTop: 16 }}>⚠️ {summaryError}</div>
                  )}
                </div>
              ) : (
                /* No summary yet */
                <div className="card">
                  <div className="card-body">
                    <div className="empty-state">
                      <div className="empty-state-icon">🤖</div>
                      <h3>Chưa có bản tóm tắt</h3>
                      <p>Nhấn nút bên dưới để AI tự động tạo bản tóm tắt lâm sàng cho bệnh nhân này.</p>
                      <button
                        className="btn btn-primary btn-lg"
                        style={{ marginTop: 20 }}
                        onClick={handleGenerate}
                        disabled={generating}
                      >
                        {generating ? (
                          <>
                            <div className="spinner" style={{ width: 18, height: 18, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: 'white' }} />
                            Đang tạo tóm tắt...
                          </>
                        ) : (
                          '🤖 Tạo tóm tắt lâm sàng'
                        )}
                      </button>
                      {summaryError && (
                        <div className="login-error" style={{ marginTop: 16, textAlign: 'left' }}>⚠️ {summaryError}</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ========== CLINICAL DATA TABS ========== */
            <div className="card animate-fade-in">
              <div className="card-header">
                <h2>{TABS.find(t => t.key === activeTab)?.icon} {TABS.find(t => t.key === activeTab)?.label}</h2>
                {currentData && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <StatusBadge status={currentData.status} />
                    <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                      {currentData.records.length} bản ghi
                    </span>
                  </div>
                )}
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                {isLoading ? (
                  <div className="loading-page"><div className="spinner" /><span>Đang tải dữ liệu...</span></div>
                ) : !currentData || currentData.records.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">📭</div>
                    <h3>Không có dữ liệu</h3>
                  </div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th style={{ width: 60 }}>#</th>
                          <th>Loại</th>
                          {getDataColumns(currentData.records).map(col => (
                            <th key={col}>{formatColumnName(col)}</th>
                          ))}
                          <th>Nguồn</th>
                        </tr>
                      </thead>
                      <tbody>
                        {currentData.records.map((record, idx) => {
                          const cols = getDataColumns(currentData.records);
                          return (
                            <tr key={idx}>
                              <td style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>{idx + 1}</td>
                              <td>
                                <span className="badge badge-teal" style={{ fontSize: 11 }}>
                                  {formatRecordType(record.record_type)}
                                </span>
                              </td>
                              {cols.map(col => (
                                <td key={col} style={{ maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {formatCellValue(record.data[col])}
                                </td>
                              ))}
                              <td style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                                {record.lineage.table}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              {/* Warnings & Limitations */}
              {currentData && (currentData.warnings.length > 0 || currentData.limitations.length > 0) && (
                <div className="card-footer">
                  {currentData.warnings.map((w, i) => (
                    <div key={`w-${i}`} style={{ fontSize: 13, color: '#92400e', marginBottom: 4 }}>⚠️ {w}</div>
                  ))}
                  {currentData.limitations.map((l, i) => (
                    <div key={`l-${i}`} style={{ fontSize: 13, color: '#1e40af', marginBottom: 4 }}>ℹ️ {l}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ========== Helper Functions ========== */

function getDataColumns(records: ClinicalRecord[]): string[] {
  const colCounts: Record<string, number> = {};
  records.forEach(r => {
    Object.keys(r.data).forEach(k => {
      colCounts[k] = (colCounts[k] || 0) + 1;
    });
  });
  // Return top columns by frequency, max 6
  return Object.entries(colCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([k]) => k);
}

function formatColumnName(col: string): string {
  return col
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/Id$/i, 'ID')
    .replace(/Hadm/i, 'HADM')
    .replace(/Icd/i, 'ICD');
}

function formatRecordType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? '✅' : '❌';
  if (typeof value === 'object') return JSON.stringify(value).slice(0, 80);
  const str = String(value);
  // Try to format datetime
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
    try {
      return new Date(str).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
    } catch {
      return str;
    }
  }
  return str;
}
