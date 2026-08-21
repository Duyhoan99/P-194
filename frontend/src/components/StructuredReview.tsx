'use client';

import { useState, useEffect, useCallback } from 'react';
import { reviews, patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import {
    FileSignature,
    CheckCircle,
    XCircle,
    Clock,
    AlertTriangle,
    Download,
    RefreshCw,
    Edit3,
    Save,
    X,
    History,
    ShieldCheck,
    Ban,
    HeartPulse
} from 'lucide-react';
import PatientCareGuideModal from './PatientCareGuideModal';

export default function StructuredReview({ patientId }: { patientId: string }) {
    const [review, setReview] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const { setFocusedCitation, setCurrentReview, selectedPatient } = useAppStore();

    // Patient Care Guide Modal
    const [showCareGuide, setShowCareGuide] = useState(false);

    // Edit mode
    const [editingClaim, setEditingClaim] = useState<string | null>(null);
    const [editText, setEditText] = useState('');
    const [editReason, setEditReason] = useState('');

    // Reject modal
    const [showRejectModal, setShowRejectModal] = useState(false);
    const [rejectReason, setRejectReason] = useState('');

    // Approve confirmation
    const [showApproveConfirm, setShowApproveConfirm] = useState(false);

    // Version history
    const [showVersions, setShowVersions] = useState(false);
    const [versions, setVersions] = useState<any[]>([]);
    const [versionsLoading, setVersionsLoading] = useState(false);

    const getSafeError = (err: any, defaultMsg: string): string => {
        if (!err) return defaultMsg;
        if (typeof err === 'string') return err;
        if (typeof err.detail === 'string') return err.detail;
        if (err.detail && typeof err.detail === 'object' && err.detail.message) return String(err.detail.message);
        if (typeof err.message === 'string') return err.message;
        return defaultMsg;
    };

    // First try to load existing review, then fall back to generate
    const loadCurrentReview = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const res = await patients.getReview(patientId);
            setReview(res);
            setCurrentReview(res);
        } catch {
            setReview(null);
            setCurrentReview(null);
        } finally {
            setLoading(false);
        }
    }, [patientId, setCurrentReview]);

    const generateReview = async () => {
        setLoading(true);
        setError('');
        try {
            const res = await patients.generateReview(patientId, ['type_2_diabetes@1.0.0']);
            setReview(res);
            setCurrentReview(res);
        } catch (err: any) {
            setError(getSafeError(err, 'Không thể tạo bản tóm tắt lâm sàng'));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadCurrentReview();
    }, [loadCurrentReview]);

    const handleCitationClick = (citOrId: any) => {
        if (typeof citOrId === 'object' && citOrId !== null) {
            setFocusedCitation(citOrId);
            return;
        }

        let citation = null;
        if (review) {
            const citations = review.draft?.citations || review.citations || [];
            citation = citations.find((c: any) => c.citation_id === citOrId);

            if (!citation && review.sections) {
                for (const sec of review.sections) {
                    if (sec.claims) {
                        for (const clm of sec.claims) {
                            if (clm.citations) {
                                const found = clm.citations.find((c: any) => c.citation_id === citOrId);
                                if (found) {
                                    citation = found;
                                    break;
                                }
                            }
                        }
                    }
                    if (citation) break;
                }
            }
        }

        if (citation) {
            setFocusedCitation(citation);
        } else {
            setFocusedCitation({
                citation_id: String(citOrId),
                source_type: 'canonical_record',
                snippet: `Trích dẫn nguồn bằng chứng [${citOrId}] từ hồ sơ y tế bệnh nhân.`,
            });
        }
    };

    // ---- Edit Claim ----
    const startEditing = (claimId: string, currentText: string) => {
        setEditingClaim(claimId);
        setEditText(currentText);
        setEditReason('');
    };

    const cancelEditing = () => {
        setEditingClaim(null);
        setEditText('');
        setEditReason('');
    };

    const saveEdit = async () => {
        if (!review || !editingClaim || !editReason.trim()) return;
        try {
            const updatedSections = review.sections.map((sec: any) => ({
                ...sec,
                claims: sec.claims?.map((c: any) =>
                    c.claim_id === editingClaim ? { ...c, text: editText } : c
                ) || [],
            }));
            const res = await reviews.edit(
                patientId,
                review.review_id,
                review.version,
                updatedSections,
                editReason
            );
            setReview(res);
            setCurrentReview(res);
            cancelEditing();
        } catch (err: any) {
            setError(getSafeError(err, 'Không thể lưu chỉnh sửa'));
        }
    };

    // ---- Approve ----
    const handleApprove = async () => {
        if (!review) return;

        // Check for missing evidence
        const hasUnverified = review.sections?.some((s: any) =>
            s.claims?.some((c: any) => c.status === 'needs_verification' || c.status === 'unsupported')
        );
        if (hasUnverified) {
            setError('Không thể ký duyệt: Vui lòng xác minh các điểm chưa có nguồn trước.');
            setShowApproveConfirm(false);
            return;
        }

        if (review.status === 'stale') {
            setError('Bản thảo đã cũ so với dữ liệu mới. Vui lòng tạo lại trước khi ký.');
            setShowApproveConfirm(false);
            return;
        }

        try {
            const res = await reviews.approve(
                patientId,
                review.review_id,
                review.review_version_id,
                review.version,
                true
            );
            setReview(res);
            setCurrentReview(res);
            setShowApproveConfirm(false);
        } catch (err: any) {
            setError(getSafeError(err, 'Ký duyệt thất bại'));
            setShowApproveConfirm(false);
        }
    };

    // ---- Reject ----
    const handleReject = async () => {
        if (!review || rejectReason.trim().length < 3) return;
        try {
            const res = await reviews.reject(
                patientId,
                review.review_id,
                review.version,
                rejectReason
            );
            setReview(res);
            setCurrentReview(res);
            setShowRejectModal(false);
            setRejectReason('');
        } catch (err: any) {
            setError(getSafeError(err, 'Từ chối thất bại'));
        }
    };

    // ---- Export ----
    const handleExport = async () => {
        if (!review) return;
        if (review.status !== 'approved') {
            setError('Chỉ có thể xuất file PDF sau khi bác sĩ đã ký duyệt.');
            return;
        }
        try {
            const blob = await reviews.exportPdf(patientId, review.review_id, review.review_version_id);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Benh_An_Lam_Sang_${patientId}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (err: any) {
            setError(getSafeError(err, 'Xuất PDF thất bại'));
        }
    };

    // ---- Version History ----
    const loadVersions = async () => {
        if (!review) return;
        setVersionsLoading(true);
        try {
            const res = await reviews.listVersions(review.review_id);
            setVersions(res.items || []);
            setShowVersions(true);
        } catch {
            setVersions([]);
            setShowVersions(true);
        } finally {
            setVersionsLoading(false);
        }
    };

    // Helper: translate medical terms into natural Vietnamese
    const cleanClaimText = (text: string) => {
        return text
            .replace(/\bTrạng thái:\s*finished\b/gi, 'Đã hoàn thành khám')
            .replace(/\bTrạng thái:\s*active\b/gi, 'Đang duy trì')
            .replace(/\bTrạng thái:\s*completed\b/gi, 'Đã kết thúc đợt')
            .replace(/\bstatus:\s*active\b/gi, 'Đang duy trì')
            .replace(/\bstatus:\s*completed\b/gi, 'Đã hoàn thành')
            .replace(/\bactive\b/g, 'đang duy trì')
            .replace(/\bcompleted\b/g, 'đã hoàn thành')
            .replace(/\bfinished\b/g, 'đã khám xong');
    };

    const cleanSectionTitle = (title: string, code?: string) => {
        const raw = (title || code || '').toLowerCase();
        if (raw.includes('overview') || raw.includes('tổng quan')) return '📋 Tổng quan Diễn tiến Bệnh nhân';
        if (raw.includes('problem') || raw.includes('tình trạng') || raw.includes('chẩn đoán')) return '🩺 Vấn đề Lâm sàng & Chẩn đoán';
        if (raw.includes('medication') || raw.includes('thuốc')) return '💊 Thuốc & Phác đồ Điều trị';
        if (raw.includes('timeline') || raw.includes('dòng thời gian')) return '⏳ Các Mốc Diễn tiến Quan trọng';
        if (raw.includes('lab') || raw.includes('kết quả') || raw.includes('trend')) return '🧪 Kết quả Cận lâm sàng Gần đây';
        if (raw.includes('conflict') || raw.includes('mâu thuẫn') || raw.includes('missing')) return '⚠️ Mâu thuẫn & Điểm cần Xác minh';
        if (raw.includes('limitation') || raw.includes('giới hạn')) return 'ℹ️ Giới hạn Dữ liệu Nguồn';
        return title || code?.replace(/_/g, ' ') || 'Thông tin Lâm sàng';
    };

    // ---- Render States ----
    if (loading && !review) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-slate-400 h-full">
                <RefreshCw className="w-8 h-8 animate-spin mb-4 text-teal-400" />
                <p className="text-sm">Đang tải bản tóm tắt lâm sàng...</p>
            </div>
        );
    }

    if (error && !review) {
        return (
            <div className="p-6 bg-rose-950/20 border border-rose-900/50 rounded-xl flex flex-col items-center justify-center h-full">
                <AlertTriangle className="w-8 h-8 text-rose-400 mb-2" />
                <p className="text-sm text-rose-300 text-center">{typeof error === 'string' ? error : (error as any)?.message || JSON.stringify(error)}</p>
                <button onClick={loadCurrentReview} className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs font-semibold text-slate-200">Thử lại</button>
            </div>
        );
    }

    if (!review) {
        return (
            <div className="flex flex-col items-center justify-center p-12 bg-slate-900/40 backdrop-blur-xl border border-slate-700/50 rounded-2xl h-full shadow-2xl">
                <div className="w-16 h-16 rounded-2xl bg-teal-500/10 flex items-center justify-center mb-5 border border-teal-500/30">
                    <FileSignature className="w-8 h-8 text-teal-400" />
                </div>
                <h3 className="text-base font-bold text-slate-200 mb-1">Chưa có Bản Tóm tắt Lâm sàng</h3>
                <p className="text-xs text-slate-400 mb-6 max-w-md text-center leading-relaxed">
                    Hệ thống sẽ đối soát toàn bộ hồ sơ điện tử (EHR) và đơn scan để tổng hợp bản tóm tắt SOAP có trích dẫn chứng cứ cho bác sĩ.
                </p>
                <button
                    onClick={generateReview}
                    disabled={loading}
                    className="px-6 py-2.5 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-teal-950/50 transition-all disabled:opacity-50"
                >
                    {loading ? 'Đang phân tích dữ liệu...' : '⚡ Khởi tạo Bản Tóm tắt Lâm sàng'}
                </button>
            </div>
        );
    }

    const sections = review.draft?.sections || review.sections || [];
    const isApproved = review.status === 'approved';
    const isStale = review.status === 'stale';
    const isRejected = review.status === 'rejected';
    const canEdit = !isApproved && !isStale;
    const canApprove = !isApproved && !isStale && !isRejected;

    const statusColor = isApproved
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
        : isStale
            ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
            : isRejected
                ? 'bg-orange-500/10 text-orange-400 border-orange-500/30'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/30';

    return (
        <div className="bg-slate-950/70 border border-white/10 rounded-2xl shadow-xl overflow-hidden flex flex-col h-full min-h-0 backdrop-blur-xl">
            {/* Header */}
            <div className="p-3.5 px-4 border-b border-white/10 bg-slate-900/90 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-teal-500/10 flex items-center justify-center border border-teal-500/30 text-teal-400">
                        <FileSignature className="w-4 h-4" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-slate-100">Bản Tóm tắt Điều trị (SOAP Summary)</h3>
                        <div className="flex items-center gap-2 mt-0.5 text-xs">
                            <span className={`px-2 py-0.5 rounded-full font-semibold border text-[11px] ${statusColor}`}>
                                {isApproved ? 'ĐÃ KÝ DUYỆT' : isStale ? 'DỮ LIỆU CŨ' : isRejected ? 'ĐÃ TỪ CHỐI' : 'BẢN THẢO (DRAFT)'}
                            </span>
                            <span className="text-slate-400 font-mono text-[11px]">Phiên bản v{review.version}</span>
                            {review.is_current_watermark === false && (
                                <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-bold">
                                    CẦN ĐỒNG BỘ LẠI
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex gap-2 items-center">
                    {error && <span className="text-xs text-rose-400 mr-2 max-w-[200px] truncate">{typeof error === 'string' ? error : (error as any)?.message || JSON.stringify(error)}</span>}

                    {/* Version History */}
                    <button
                        onClick={loadVersions}
                        className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
                        title="Lịch sử các phiên bản"
                    >
                        <History className="w-4 h-4" />
                    </button>

                    {/* Regenerate */}
                    <button
                        onClick={generateReview}
                        className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
                        title="Tạo lại bản thảo từ dữ liệu mới nhất"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Disclaimer */}
            {review.disclaimer && (
                <div className="px-4 py-2 bg-slate-950/90 border-b border-white/5 flex items-center gap-2">
                    <ShieldCheck className="w-3.5 h-3.5 text-teal-400/80 shrink-0" />
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                        Tài liệu hỗ trợ rà soát lâm sàng. Bác sĩ kiểm tra chứng cứ nguồn và chịu trách nhiệm chuyên môn trước khi ký duyệt.
                    </p>
                </div>
            )}

            {/* Content: Clean Medical Prose without heavy box borders */}
            <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-6 chat-scrollbar pr-3">
                {sections.map((section: any, idx: number) => (
                    <div
                        key={section.section_code || idx}
                        className="space-y-2 bg-slate-900/40 p-4 rounded-xl border border-slate-800/80"
                    >
                        <h4 className="text-xs font-bold text-teal-300 uppercase tracking-wider flex items-center gap-2 pb-1.5 border-b border-slate-800/60">
                            {cleanSectionTitle(section.title, section.section_code)}
                        </h4>

                        <div className="space-y-2 pt-1">
                            {section.claims && section.claims.length > 0 ? (
                                section.claims.map((claim: any) => (
                                    <div
                                        key={claim.claim_id}
                                        className="py-1 px-2 rounded-lg text-xs sm:text-sm text-slate-200 leading-relaxed hover:bg-slate-800/40 transition-colors group relative flex items-start gap-2.5"
                                    >
                                        <span className="text-teal-500 font-bold text-xs mt-0.5 shrink-0">•</span>

                                        <div className="flex-1 min-w-0">
                                            {editingClaim === claim.claim_id ? (
                                                /* --- EDIT MODE --- */
                                                <div className="space-y-3 p-3 bg-slate-900 rounded-lg border border-teal-500/40 my-1">
                                                    <textarea
                                                        value={editText}
                                                        onChange={(e) => setEditText(e.target.value)}
                                                        className="w-full bg-slate-950 border border-teal-700/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500 min-h-[80px] resize-y"
                                                    />
                                                    <input
                                                        type="text"
                                                        value={editReason}
                                                        onChange={(e) => setEditReason(e.target.value)}
                                                        placeholder="Lý do chỉnh sửa (bắt buộc)..."
                                                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-teal-500"
                                                    />
                                                    <div className="flex gap-2">
                                                        <button
                                                            onClick={saveEdit}
                                                            disabled={!editReason.trim()}
                                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium rounded-md disabled:opacity-50 transition-colors"
                                                        >
                                                            <Save className="w-3 h-3" /> Lưu thay đổi
                                                        </button>
                                                        <button
                                                            onClick={cancelEditing}
                                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-md transition-colors"
                                                        >
                                                            <X className="w-3 h-3" /> Hủy
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                /* --- VIEW MODE --- */
                                                <div className="inline">
                                                    <span>{cleanClaimText(claim.text)}</span>

                                                    {/* Citation Badges */}
                                                    {claim.citations && claim.citations.length > 0 && (
                                                        <span className="inline-flex gap-1 ml-2 align-middle">
                                                            {claim.citations.map((cit: any, citIdx: number) => (
                                                                <button
                                                                    key={`${cit.citation_id || cit.evidence_id || 'cit'}-${citIdx}`}
                                                                    onClick={() => handleCitationClick(cit)}
                                                                    className="inline-flex items-center justify-center min-w-[22px] h-[20px] px-1.5 text-[10px] font-bold font-mono bg-teal-950/80 hover:bg-teal-900 text-teal-300 border border-teal-700/60 hover:border-teal-400 rounded-md cursor-pointer transition-all shadow-sm"
                                                                    title="Nhấp để xem chứng cứ nguồn gốc"
                                                                >
                                                                    {cit.citation_id?.split('-').pop()?.substring(0, 4) || `[${citIdx + 1}]`}
                                                                </button>
                                                            ))}
                                                        </span>
                                                    )}

                                                    {claim.status === 'needs_verification' && (
                                                        <span className="inline-flex items-center gap-1 ml-2 text-[10px] uppercase font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                                                            <AlertTriangle className="w-3 h-3" /> Cần xác minh
                                                        </span>
                                                    )}

                                                    {claim.status === 'unsupported' && (
                                                        <span className="inline-flex items-center gap-1 ml-2 text-[10px] uppercase font-bold text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/30">
                                                            <XCircle className="w-3 h-3" /> Chưa có nguồn
                                                        </span>
                                                    )}

                                                    {/* Edit button */}
                                                    {canEdit && (
                                                        <button
                                                            onClick={() => startEditing(claim.claim_id, claim.text)}
                                                            className="inline-block ml-2 p-1 opacity-0 group-hover:opacity-100 text-slate-400 hover:text-teal-300 rounded transition-all hover:bg-slate-800 align-middle"
                                                            title="Sửa nội dung claim này"
                                                        >
                                                            <Edit3 className="w-3 h-3" />
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <p className="text-xs text-slate-500 italic pl-4">Chưa ghi nhận thông tin trong đợt này.</p>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* STICKY BOTTOM ACTION BAR: Always visible for 1-click Doctor Approval & Export */}
            <div className="p-3 px-5 border-t border-white/10 bg-slate-950/95 flex items-center justify-between shrink-0 flex-wrap gap-2 shadow-2xl backdrop-blur-xl">
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">
                        {isApproved ? '✓ Đã hoàn tất phê duyệt chuyên môn' : '⚠️ Bản thảo đang chờ bác sĩ rà soát & ký số'}
                    </span>
                </div>

                <div className="flex items-center gap-2.5 flex-wrap">
                    {/* Patient Care Plan / Voice Guide Button */}
                    <button
                        onClick={() => setShowCareGuide(true)}
                        className="flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-purple-600/90 via-indigo-600/90 to-teal-600/90 hover:from-purple-500 hover:to-teal-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-purple-950/40 border border-white/10"
                        title="Tạo phiếu hướng dẫn ăn uống, vận động & dặn dò bằng giọng nói cho người bệnh"
                    >
                        <HeartPulse className="w-4 h-4 text-pink-300" />
                        <span>Hướng Dẫn Bệnh Nhân (Care Plan)</span>
                    </button>

                    {/* Reject */}
                    {canApprove && (
                        <button
                            onClick={() => setShowRejectModal(true)}
                            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-900 hover:bg-rose-950/50 border border-slate-700 hover:border-rose-700 text-slate-300 hover:text-rose-300 text-xs font-semibold rounded-xl transition-all"
                        >
                            <Ban className="w-3.5 h-3.5" /> Yêu cầu chỉnh sửa
                        </button>
                    )}

                    {/* Approve */}
                    {canApprove && (
                        <button
                            onClick={() => setShowApproveConfirm(true)}
                            className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-emerald-950/40"
                        >
                            <CheckCircle className="w-4 h-4" /> Ký duyệt Bệnh án
                        </button>
                    )}

                    {/* Export PDF */}
                    {isApproved && (
                        <button
                            onClick={handleExport}
                            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-teal-950/40"
                        >
                            <Download className="w-4 h-4" /> Xuất File Bệnh án PDF
                        </button>
                    )}
                </div>
            </div>

            {/* Patient Care Plan Modal */}
            <PatientCareGuideModal
                patient={selectedPatient}
                patientId={patientId}
                review={review}
                isOpen={showCareGuide}
                onClose={() => setShowCareGuide(false)}
            />

            {/* Approve Confirmation Modal */}
            {showApproveConfirm && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-100 text-sm">Xác nhận Ký duyệt Bệnh án</h3>
                                <p className="text-xs text-slate-400">Bản tóm tắt sẽ được lưu vào Patient Memory và đóng dấu số</p>
                            </div>
                        </div>
                        <p className="text-xs text-slate-300 mb-6 leading-relaxed">
                            Bác sĩ xác nhận đã rà soát toàn bộ diễn tiến, chỉ số xét nghiệm và đơn thuốc được đối chiếu với chứng cứ gốc.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowApproveConfirm(false)}
                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition-colors"
                            >
                                Hủy bỏ
                            </button>
                            <button
                                onClick={handleApprove}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition-colors shadow-lg shadow-emerald-900/30"
                            >
                                Xác nhận Ký số
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Reject Modal */}
            {showRejectModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-rose-500/10 flex items-center justify-center border border-rose-500/20">
                                <Ban className="w-5 h-5 text-rose-400" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-100 text-sm">Yêu cầu Chỉnh sửa / Từ chối</h3>
                                <p className="text-xs text-slate-400">Vui lòng nhập lý do từ chối bản tóm tắt này</p>
                            </div>
                        </div>
                        <textarea
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="Nhập lý do cần chỉnh sửa (tối thiểu 3 ký tự)..."
                            className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-xs text-slate-200 focus:outline-none focus:border-rose-500 min-h-[100px] resize-y mb-4"
                        />
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => { setShowRejectModal(false); setRejectReason(''); }}
                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition-colors"
                            >
                                Hủy bỏ
                            </button>
                            <button
                                onClick={handleReject}
                                disabled={rejectReason.trim().length < 3}
                                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-xl transition-colors shadow-lg shadow-rose-900/30 disabled:opacity-50"
                            >
                                Gửi yêu cầu
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Version History Modal */}
            {showVersions && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-lg w-full mx-4 shadow-2xl max-h-[80vh] flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <History className="w-5 h-5 text-cyan-400" />
                                <h3 className="font-bold text-slate-100 text-sm">Lịch sử Phiên bản</h3>
                            </div>
                            <button onClick={() => setShowVersions(false)} className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800">
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto space-y-2 chat-scrollbar pr-1">
                            {versionsLoading ? (
                                <p className="text-xs text-slate-400 text-center py-6">Đang tải lịch sử...</p>
                            ) : versions.length === 0 ? (
                                <p className="text-xs text-slate-500 text-center py-6">Chỉ có 1 phiên bản hiện tại.</p>
                            ) : (
                                versions.map((v: any) => (
                                    <div key={v.review_version_id} className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between text-xs">
                                        <div>
                                            <div className="font-bold text-slate-200">Phiên bản v{v.version}</div>
                                            <div className="text-[11px] text-slate-400">
                                                {v.created_by || 'Hệ thống'} • {new Date(v.created_at).toLocaleString('vi-VN')}
                                            </div>
                                        </div>
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                            v.status === 'approved' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-800 text-slate-400 border-slate-700'
                                        }`}>
                                            {v.status === 'approved' ? 'ĐÃ DUYỆT' : 'BẢN CŨ'}
                                        </span>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
