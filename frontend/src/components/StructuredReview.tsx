'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { reviews, patients } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import {
    FileSignature,
    CheckCircle,
    XCircle,
    AlertTriangle,
    Download,
    RefreshCw,
    Edit3,
    Save,
    X,
    History,
    ShieldCheck,
    Ban,
    HeartPulse,
    Eye,
    RotateCcw,
    Trash2
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
    const loadedPatientRef = useRef<string | null>(null);

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
            // Auto generate review if it doesn't exist yet for new patients
            try {
                const res = await patients.generateReview(patientId, ['type_2_diabetes@1.0.0']);
                setReview(res);
                setCurrentReview(res);
            } catch (genErr: any) {
                setReview(null);
                setCurrentReview(null);
            }
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
            setError(getSafeError(err, 'Không thể tạo bản tóm tắt lâm sàng. Vui lòng thử lại.'));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (loadedPatientRef.current === patientId) return;
        loadedPatientRef.current = patientId;
        void loadCurrentReview();
    }, [loadCurrentReview, patientId]);

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
        if (!review || !editingClaim) return;
        const finalReason = editReason.trim() || 'Bác sĩ điều chỉnh thông tin lâm sàng';
        try {
            const rawSections = review.sections || review.draft?.sections || [];
            const updatedSections = rawSections.map((sec: any) => ({
                section_code: sec.section_code,
                title: sec.title,
                clinician_text: sec.clinician_text,
                claims: sec.claims?.map((c: any) =>
                    c.claim_id === editingClaim ? { ...c, text: editText.trim() } : c
                ) || [],
            }));
            const res = await reviews.edit(
                patientId,
                review.review_id,
                review.version,
                updatedSections,
                finalReason
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
        if (!review) return;
        const finalReason = rejectReason.trim() || 'Bác sĩ từ chối bản rà soát';
        if (finalReason.length < 3) {
            setError('Lý do từ chối phải có tối thiểu 3 ký tự.');
            return;
        }
        try {
            const res = await reviews.reject(
                patientId,
                review.review_id,
                review.version,
                finalReason,
                review.review_version_id
            );
            setReview(res);
            setCurrentReview(res);
            setShowRejectModal(false);
            setRejectReason('');
        } catch (err: any) {
            setError(getSafeError(err, 'Từ chối thất bại'));
        }
    };

    // Export modal state
    const [showExportModal, setShowExportModal] = useState(false);
    const [customExportName, setCustomExportName] = useState('');

    // ---- Export ----
    const openExportModal = () => {
        if (!review) return;
        if (review.status !== 'approved') {
            setError('Chỉ có thể xuất file PDF sau khi bác sĩ đã ký duyệt.');
            return;
        }
        const patientNameClean = (selectedPatient?.pseudonym || patientId).replace(/\s+/g, '_');
        const defaultName = `Tom_tat_dieu_tri_${patientNameClean}_${patientId}_v${review.version}.pdf`;
        setCustomExportName(defaultName);
        setShowExportModal(true);
    };

    const handleExport = async () => {
        if (!review) return;
        setError('');
        try {
            const blob = await reviews.exportPdf(patientId, review.review_id, review.review_version_id);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            let finalName = customExportName.trim() || `Tom_tat_dieu_tri_${patientId}_v${review.version}.pdf`;
            if (!finalName.toLowerCase().endsWith('.pdf')) {
                finalName += '.pdf';
            }
            a.download = finalName;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            setShowExportModal(false);
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

    const handleSelectVersion = async (targetVersion: number) => {
        setLoading(true);
        setShowVersions(false);
        setError('');
        try {
            const res = await patients.getReview(patientId, targetVersion);
            if (res) {
                setReview(res);
                setCurrentReview(res);
            }
        } catch (err: any) {
            setError(getSafeError(err, `Không thể tải phiên bản v${targetVersion}`));
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteVersion = async (reviewVersionId: string, versionNum: number) => {
        if (!review) return;
        if (!window.confirm(`Xóa phiên bản v${versionNum}? Hành động này không thể hoàn tác.`)) return;
        try {
            await reviews.deleteVersion(review.review_id, reviewVersionId);
            // Reload version list
            const res = await reviews.listVersions(review.review_id);
            setVersions(res.items || []);
        } catch (err: any) {
            alert(getSafeError(err, `Không thể xóa phiên bản v${versionNum}`));
        }
    };

    const isDisclaimerOrAdministrative = (text: string) => {
        const t = (text || '').toUpperCase();
        const markers = [
            'DỮ LIỆU GIẢ LẬP',
            'DU LIEU GIA LAP',
            'KHÔNG PHẢI HỒ SƠ Y TẾ THẬT',
            'KHONG PHAI HO SO Y TE THAT',
            'PHỤC VỤ DEMO',
            'PHUC VU DEMO',
            'DEMO ONLY',
            'SYNTHETIC DATA',
            'DỮ LIỆU MÔ PHỎNG',
            'TRUNG TÂM Y KHOA SYNTHETIC',
            'MÃ TÀI LIỆU DOC-',
            'MÃ TÀI LIỆU',
            'MÃ TIẾP NHẬN REQ-',
            'MÃ TIẾP NHẬN',
            'DANH SÁCH VẤN ĐỀ HÀNH CHÍNH',
            'KHÔNG TẠO SỰ KIỆN LÂM SÀNG',
            'METADATA HÀNH CHÍNH',
            'NGÀY SINH / GIỚI TÍNH',
            'NGÀY SINH/GIỚI TÍNH',
            'NGÀY TÀI LIỆU',
            'CHẨN ĐOÁN ĐÃ GHI NHẬN TRONG HỒ SƠ',
            'CHẨN ĐOÁN ĐÃ GHI NHẬN',
            'MÃ SNOMED CT',
            'MÃ SNOMED',
            'TÊN BỆNH GHI NHẬN TỪ',
            'ĐỐI CHIẾU THUỐC TRONG HỒ SƠ',
            'BẢNG NÀY MÔ TẢ TRẠNG THÁI',
            'PHIẾU KẾT QUẢ XÉT NGHIỆM',
            'GHI CHÚ TÁI KHÁM ĐƠN VỊ',
        ];
        return markers.some(m => t.includes(m));
    };

    const cleanClaimText = (text: string) => {
        return text
            .replace(/DỮ LIỆU GIẢ LẬP PHỤC VỤ DEMO\s*[-–—:]*\s*KHÔNG PHẢI HỒ SƠ Y TẾ THẬT/gi, '')
            .replace(/DỮ LIỆU GIẢ LẬP PHỤC VỤ DEMO/gi, '')
            .replace(/KHÔNG PHẢI HỒ SƠ Y TẾ THẬT/gi, '')
            .replace(/DU LIEU GIA LAP PHUC VU DEMO/gi, '')
            .replace(/KHONG PHAI HO SO Y TE THAT/gi, '')
            .replace(/DEMO ONLY/gi, '')
            .replace(/SYNTHETIC DATA/gi, '')
            .replace(/Đơn vị\s+Trung tâm Y khoa Synthetic\s*[-–—:]*\s*Khoa Nội tổng hợp/gi, '')
            .replace(/Mã tài liệu\s+DOC-[A-Z0-9_-]+/gi, '')
            .replace(/Mã bệnh nhân\s+[A-Z0-9_-]+/gi, '')
            .replace(/Tên synthetic\s+[^\n.,;]+/gi, '')
            .replace(/\bTrạng thái:\s*finished\b/gi, 'Đã hoàn thành khám')
            .replace(/\bTrạng thái:\s*active\b/gi, 'Đang duy trì')
            .replace(/\bTrạng thái:\s*completed\b/gi, 'Đã kết thúc đợt')
            .replace(/\bstatus:\s*active\b/gi, 'Đang duy trì')
            .replace(/\bstatus:\s*completed\b/gi, 'Đã hoàn thành')
            .replace(/\bactive\b/g, 'đang duy trì')
            .replace(/\bcompleted\b/g, 'đã hoàn thành')
            .replace(/\bfinished\b/g, 'đã khám xong')
            .trim();
    };

    const renderClaimContent = (rawText: string) => {
        const cleaned = cleanClaimText(rawText);
        const colonIdx = cleaned.indexOf(':');
        if (colonIdx !== -1 && colonIdx < 45) {
            const label = cleaned.slice(0, colonIdx + 1);
            const value = cleaned.slice(colonIdx + 1);
            return (
                <span>
                    <strong className="text-teal-800 dark:text-teal-300 font-semibold">{label}</strong>
                    <span className="text-slate-900 dark:text-slate-100 font-medium">{value}</span>
                </span>
            );
        }
        return <span className="text-slate-900 dark:text-slate-100 font-medium">{cleaned}</span>;
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
            <div className="flex flex-col items-center justify-center p-12 clinical-card/40 backdrop-blur-xl border border-slate-700/50 rounded-2xl h-full shadow-2xl">
                <div className="w-16 h-16 rounded-2xl bg-teal-500/10 flex items-center justify-center mb-4 border border-teal-500/30 text-teal-400">
                    <FileSignature className="w-8 h-8" />
                </div>
                <h3 className="text-base font-bold text-slate-100 mb-1">Tổng hợp Bản Tóm tắt Lâm sàng (SOAP)</h3>
                <p className="text-xs text-slate-400 mb-6 max-w-md text-center leading-relaxed">
                    Nhấn nút bên dưới để AI tự động đối soát toàn bộ dữ liệu đa nguồn và tạo bản tóm tắt lâm sàng chuẩn y khoa.
                </p>
                <button
                    onClick={generateReview}
                    disabled={loading}
                    className="px-6 py-2.5 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white text-xs font-bold rounded-xl shadow-lg transition-all disabled:opacity-50 cursor-pointer"
                >
                    {loading ? 'Đang phân tích và tạo tóm tắt...' : '⚡ Khởi tạo Bản Tóm tắt Lâm sàng'}
                </button>
            </div>
        );
    }

    if (!review) {
        return (
            <div className="flex flex-col items-center justify-center p-12 clinical-card/40 backdrop-blur-xl border border-slate-700/50 rounded-2xl h-full shadow-2xl">
                <div className="w-16 h-16 rounded-2xl bg-teal-500/10 flex items-center justify-center mb-5 border border-teal-500/30">
                    <FileSignature className="w-8 h-8 text-teal-400" />
                </div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-1">Chưa có Bản Tóm tắt Lâm sàng</h3>
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
        <div className="clinical-card overflow-hidden flex flex-col h-full max-h-[calc(100dvh-13rem)] min-h-0">
            {/* Header */}
            <div className="p-3.5 px-4 border-b flex items-center justify-between shrink-0 border-[var(--border-card)] bg-[var(--bg-card)]">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-teal-500/10 flex items-center justify-center border border-teal-500/30 text-teal-400">
                        <FileSignature className="w-4 h-4" />
                    </div>
                    <div>
                        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Bản Tóm tắt Điều trị (SOAP Summary)</h3>
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
                <div className="px-4 py-2 bg-[var(--bg-subcard)] border-b border-[var(--border-card)] flex items-center gap-2">
                    <ShieldCheck className="w-3.5 h-3.5 text-teal-400/80 shrink-0" />
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                        Tài liệu hỗ trợ rà soát lâm sàng. Bác sĩ kiểm tra chứng cứ nguồn và chịu trách nhiệm chuyên môn trước khi ký duyệt.
                    </p>
                </div>
            )}

            {/* Banner when viewing an older version */}
            {(review.status === 'stale' || review.status === 'rejected') && (
                <div className="px-4 py-2 bg-amber-500/10 border-b border-amber-500/20 flex items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2 text-amber-300">
                        <History className="w-4 h-4 text-amber-400 shrink-0" />
                        <span>Bạn đang xem bản lưu lịch sử <strong>v{review.version}</strong> ({review.status === 'stale' ? 'Bản cũ' : 'Đã từ chối'}).</span>
                    </div>
                    <button
                        onClick={loadCurrentReview}
                        className="px-2.5 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/30 rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all"
                    >
                        <RotateCcw className="w-3 h-3" />
                        <span>Về bản mới nhất</span>
                    </button>
                </div>
            )}

            {/* Content: Clean Medical Prose without heavy box borders */}
            <div
                className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-5 space-y-6 summary-scrollbar pr-3 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-teal-400/60"
                role="region"
                aria-label="Nội dung bản tóm tắt điều trị"
                tabIndex={0}
            >
                {sections.map((section: any, idx: number) => {
                    const cleanClaims = (() => {
                        if (!section.claims || section.claims.length === 0) return [];
                        const cleanTrendText = (text: string) => {
                            if (!text || !text.includes(';')) return text;
                            const parts = text.split(';').map((p: string) => p.trim());
                            const seen = new Set<string>();
                            const uniqueParts: string[] = [];
                            for (const p of parts) {
                                const normP = p.replace(/(\d+)\.0(?=\s|$|[^\d])/g, '$1').replace(/\s+/g, ' ').toLowerCase();
                                if (!seen.has(normP)) {
                                    seen.add(normP);
                                    uniqueParts.push(p);
                                }
                            }
                            return uniqueParts.join('; ');
                        };

                        const getSemanticKey = (text: string, secCode?: string) => {
                            const t = text.toLowerCase().replace(/(\d+)\.0(?=\s|$|[^\d])/g, '$1').replace(/\s+/g, ' ').trim();
                            if (secCode === 'current_medications' || t.includes('thuốc')) {
                                const cleanMed = t.replace(/\b\d{4}-\d{2}-\d{2}\b/g, '')
                                                  .replace(/thuốc(?:\s+hiện\s+tại)?:\s*/gi, '')
                                                  .replace(/ngày\s*[:\d\-\/]*/gi, '')
                                                  .replace(/(?:trạng thái|ghi nhận|đang duy trì|đang sử dụng|active|stopped|discontinued).*/gi, '')
                                                  .replace(/\(.*?\)/g, '')
                                                  .trim();
                                const drugMatch = cleanMed.match(/^([a-zA-Zà-ỹÀ-Ỹ\s]+)/i);
                                const drugBase = (drugMatch ? drugMatch[1] : cleanMed).trim().split(/\s+/)[0].toLowerCase();
                                return `med:${drugBase || cleanMed}`;
                            }
                            if (secCode === 'recent_results' || t.includes('xét nghiệm') || t.includes('kết quả')) {
                                const dateMatch = t.match(/\b(\d{4}-\d{2}-\d{2})\b/);
                                const dateKey = dateMatch ? dateMatch[1] : 'no_date';
                                const withoutDate = t.replace(/\b\d{4}-\d{2}-\d{2}\b/g, '');

                                const valMatch = withoutDate.match(/(?:kết quả|kết quả:|\:)\s*(\d+(?:\.\d+)?)/i) || 
                                                 withoutDate.match(/(\d+(?:\.\d+)?)\s*(?:%|mmol\/l|µmol\/l|umol\/l|mg\/dl|ml\/min|mmhg|mm\[hg\])?/i);
                                const valNorm = (valMatch ? valMatch[1] : '').replace(/\.0$/, '');

                                let testKey = 'lab';
                                if (withoutDate.includes('hba1c')) testKey = 'hba1c';
                                else if (withoutDate.includes('glucose') || withoutDate.includes('đường huyết')) testKey = 'glucose';
                                else if (withoutDate.includes('creatinine')) testKey = 'creatinine';
                                else if (withoutDate.includes('egfr')) testKey = 'egfr';
                                else if (withoutDate.includes('tâm thu') || withoutDate.includes('systolic')) testKey = 'bp_sys';
                                else if (withoutDate.includes('tâm trương') || withoutDate.includes('diastolic')) testKey = 'bp_dia';
                                else if (withoutDate.includes('huyết áp') || withoutDate.includes('blood pressure')) {
                                    const num = parseFloat(valNorm);
                                    testKey = (!isNaN(num) && num >= 100) ? 'bp_sys' : 'bp_dia';
                                } else {
                                    testKey = withoutDate.replace(/xét nghiệm:?/i, '').replace(/kết quả:?.*/i, '').trim().slice(0, 20);
                                }
                                return `lab:${testKey}:${dateKey}:${valNorm}`;
                            }
                            if (secCode === 'active_conditions' || t.includes('chẩn đoán')) {
                                const cond = t.replace(/\(.*?\)/g, '').replace(/chẩn đoán\/tình trạng bệnh:\s*/g, '').replace(/ghi nhận\s+\d{4}-\d{2}-\d{2}/g, '').trim();
                                return `cond:${cond}`;
                            }
                            if (secCode === 'patient_overview' || t.includes('khám') || t.includes('lượt khám') || t.includes('tái khám')) {
                                const dateMatch = t.match(/\b(\d{4}-\d{2}-\d{2})\b/);
                                const dateKey = dateMatch ? dateMatch[1] : 'enc';
                                return `enc:${dateKey}`;
                            }
                            return `claim:${t}`;
                        };

                        const hasDosage = (str: string) => /\d+\s*(?:mg|g|ml|mcg|ui|iu)/i.test(str);
                        const isBetterMedText = (candidate: string, current: string) => {
                            if (hasDosage(candidate) && !hasDosage(current)) return true;
                            if (!hasDosage(candidate) && hasDosage(current)) return false;
                            if (candidate.startsWith('Thuốc hiện tại:') && !current.startsWith('Thuốc hiện tại:')) return true;
                            return candidate.length > current.length;
                        };

                        const claimMap = new Map<string, any>();
                        for (const claim of section.claims) {
                            if (isDisclaimerOrAdministrative(claim.text || '')) {
                                continue;
                            }
                            let cleanedText = cleanTrendText(cleanClaimText(claim.text || ''))
                                .replace(/Lượt khám GHI CHÚ TÁI KHÁM/gi, 'Lần tái khám')
                                .replace(/Lượt khám Ghi chú tái khám/gi, 'Lần tái khám')
                                .replace(/Lượt khám Tái khám/gi, 'Lần tái khám')
                                .replace(/Lượt khám khám/gi, 'Lần khám');
                            if (!cleanedText) continue;
                            const semKey = getSemanticKey(cleanedText, section.section_code);

                            if (!claimMap.has(semKey)) {
                                claimMap.set(semKey, { ...claim, text: cleanedText, citations: [...(claim.citations || [])] });
                            } else {
                                const existing = claimMap.get(semKey);
                                if (section.section_code === 'current_medications' || cleanedText.toLowerCase().includes('thuốc')) {
                                    if (isBetterMedText(cleanedText, existing.text)) {
                                        existing.text = cleanedText;
                                    }
                                } else if (cleanedText.startsWith('Lần tái khám') && !existing.text.startsWith('Lần tái khám')) {
                                    existing.text = cleanedText;
                                } else if (existing.text.length > cleanedText.length && (cleanedText.includes('BP Systolic') || cleanedText.includes('BP Diastolic') || cleanedText.startsWith('Thuốc:'))) {
                                    existing.text = cleanedText;
                                }
                                const seenCitIds = new Set(existing.citations.map((c: any) => c.citation_id || c.resource_id || c.document_id));
                                for (const cit of (claim.citations || [])) {
                                    const cid = cit.citation_id || cit.resource_id || cit.document_id;
                                    if (cid && !seenCitIds.has(cid)) {
                                        seenCitIds.add(cid);
                                        existing.citations.push(cit);
                                    }
                                }
                            }
                        }
                        return Array.from(claimMap.values());
                    })();

                    return (
                    <div
                        key={section.section_code || idx}
                        className="space-y-2 clinical-subcard p-4 rounded-xl"
                    >
                        <h4 className="text-xs font-bold text-teal-700 dark:text-teal-300 uppercase tracking-wider font-extrabold flex items-center gap-2 pb-1.5 border-b border-[var(--border-card)]">
                            {cleanSectionTitle(section.title, section.section_code)}
                        </h4>

                        <div className="space-y-2 pt-1">
                            {cleanClaims.length > 0 ? (
                                cleanClaims.map((claim: any) => (
                                    <div
                                        key={claim.claim_id}
                                        className="py-1.5 px-2.5 rounded-lg text-xs sm:text-sm text-slate-900 dark:text-slate-100 font-normal leading-relaxed hover:bg-[var(--accent-teal-bg)] transition-colors group relative flex items-start gap-2.5"
                                    >
                                        <span className="text-teal-500 dark:text-teal-400 font-bold text-sm mt-0.5 shrink-0">•</span>

                                        <div className="flex-1 min-w-0">
                                            {editingClaim === claim.claim_id ? (
                                                /* --- EDIT MODE --- */
                                                <div className="space-y-3 p-3 clinical-card rounded-lg border border-teal-500/40 my-1">
                                                    <textarea
                                                        value={editText}
                                                        onChange={(e) => setEditText(e.target.value)}
                                                        className="w-full clinical-input border border-teal-700/50 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:border-teal-500 min-h-[80px] resize-y"
                                                    />
                                                    <input
                                                        type="text"
                                                        value={editReason}
                                                        onChange={(e) => setEditReason(e.target.value)}
                                                        placeholder="Lý do chỉnh sửa (bắt buộc)..."
                                                        className="w-full clinical-input border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-teal-500"
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
                                                    {renderClaimContent(claim.text)}

                                                    {/* Citation Badges with Format Indicators (FHIR, PDF, OCR, EHR) */}
                                                    {claim.citations && claim.citations.length > 0 && (
                                                        <span className="inline-flex flex-wrap gap-1.5 ml-2 align-middle">
                                                            {claim.citations.map((cit: any, citIdx: number) => {
                                                                const rawType = (cit.source_type || '').toLowerCase();
                                                                const docName = (cit.document_name || cit.document_id || cit.citation_id || '').toLowerCase();
                                                                const resType = (cit.resource_type || '').toLowerCase();

                                                                let label = 'PDF';
                                                                let colorCls = 'bg-indigo-950/90 text-indigo-300 border-indigo-600/80 hover:border-indigo-300 shadow-[0_0_8px_rgba(99,102,241,0.2)]';
                                                                let icon = '📄';

                                                                if (rawType === 'ocr' || docName.includes('scan') || docName.includes('photo') || docName.endsWith('.jpg') || docName.endsWith('.png') || docName.endsWith('.jpeg')) {
                                                                    label = 'OCR';
                                                                    colorCls = 'bg-amber-950/90 text-amber-300 border-amber-600/80 hover:border-amber-300 shadow-[0_0_8px_rgba(245,158,11,0.2)]';
                                                                    icon = '📷';
                                                                } else if (rawType === 'pdf' || docName.includes('pdf') || docName.endsWith('.pdf') || docName.includes('doc_') || docName.includes('prescription') || docName.includes('phieu_kham') || docName.includes('followup') || docName.includes('lab_report')) {
                                                                    label = 'PDF';
                                                                    colorCls = 'bg-indigo-950/90 text-indigo-300 border-indigo-600/80 hover:border-indigo-300 shadow-[0_0_8px_rgba(99,102,241,0.2)]';
                                                                    icon = '📄';
                                                                } else if (rawType === 'fhir' || docName.includes('fhir') || docName.endsWith('.json') || docName.includes('bundle') || cit.resource_type || cit.resource_id) {
                                                                    label = 'FHIR';
                                                                    colorCls = 'bg-cyan-950/90 text-cyan-300 border-cyan-600/80 hover:border-cyan-300 shadow-[0_0_8px_rgba(6,182,212,0.2)]';
                                                                    icon = '⚡';
                                                                } else if (rawType === 'canonical_record' || rawType === 'ehr') {
                                                                    label = 'EHR';
                                                                    colorCls = 'bg-emerald-950/90 text-emerald-300 border-emerald-600/80 hover:border-emerald-300 shadow-[0_0_8px_rgba(16,185,129,0.2)]';
                                                                    icon = '🏥';
                                                                }

                                                                return (
                                                                    <button
                                                                        key={`${cit.citation_id || cit.evidence_id || 'cit'}-${citIdx}`}
                                                                        onClick={() => handleCitationClick(cit)}
                                                                        className={`inline-flex items-center gap-1 min-w-[34px] h-[20px] px-1.5 text-[10px] font-extrabold font-mono border rounded-md cursor-pointer transition-all ${colorCls}`}
                                                                        title={`Nhấp để mở nguồn chứng cứ gốc [${label}]`}
                                                                    >
                                                                        <span>{icon}</span>
                                                                        <span>{label}</span>
                                                                        {claim.citations.length > 1 && <span className="opacity-75 text-[9px]">#{citIdx + 1}</span>}
                                                                    </button>
                                                                );
                                                            })}
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
                );
                })}
            </div>

            {/* STICKY BOTTOM ACTION BAR: Always visible for 1-click Doctor Approval & Export */}
            <div className="p-3 px-5 border-t border-white/10 clinical-input/95 flex items-center justify-between shrink-0 flex-wrap gap-2 shadow-2xl backdrop-blur-xl">
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">
                        {isApproved ? '✓ Đã hoàn tất phê duyệt chuyên môn' : '⚠️ Bản thảo đang chờ bác sĩ rà soát & ký số'}
                    </span>
                </div>

                <div className="flex items-center gap-2.5 flex-wrap">
                    {/* Patient Care Plan / Voice Guide Button */}
                    <button
                        onClick={() => setShowCareGuide(true)}
                        disabled={!isApproved}
                        aria-disabled={!isApproved}
                        className="flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-purple-600/90 via-indigo-600/90 to-teal-600/90 hover:from-purple-500 hover:to-teal-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-purple-950/40 border border-white/10 disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:from-purple-600/90 disabled:hover:to-teal-600/90"
                        title={isApproved
                            ? 'Tạo phiếu hướng dẫn ăn uống, vận động và dặn dò cho người bệnh'
                            : 'Cần xử lý các điểm chưa xác minh và ký duyệt bản tóm tắt trước khi tạo hướng dẫn'}
                    >
                        <HeartPulse className="w-4 h-4 text-pink-300" />
                        <span>Hướng Dẫn Bệnh Nhân (Care Plan)</span>
                    </button>

                    {/* Reject */}
                    {canApprove && (
                        <button
                            onClick={() => setShowRejectModal(true)}
                            className="flex items-center gap-1.5 px-3.5 py-2 clinical-card hover:bg-rose-950/50 border border-slate-700 hover:border-rose-700 text-slate-300 hover:text-rose-300 text-xs font-semibold rounded-xl transition-all"
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
                            onClick={openExportModal}
                            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-teal-950/40 cursor-pointer"
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
                    <div className="clinical-card border border-slate-700 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">Xác nhận Ký duyệt Bệnh án</h3>
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
                    <div className="clinical-card border border-slate-700 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-rose-500/10 flex items-center justify-center border border-rose-500/20">
                                <Ban className="w-5 h-5 text-rose-400" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">Yêu cầu Chỉnh sửa / Từ chối</h3>
                                <p className="text-xs text-slate-400">Vui lòng nhập lý do từ chối bản tóm tắt này</p>
                            </div>
                        </div>
                        <textarea
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="Nhập lý do cần chỉnh sửa (tối thiểu 3 ký tự)..."
                            className="w-full clinical-input border border-slate-700 rounded-xl px-4 py-3 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-rose-500 min-h-[100px] resize-y mb-4"
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
                    <div className="clinical-card border border-slate-700 rounded-2xl p-6 max-w-lg w-full mx-4 shadow-2xl max-h-[80vh] flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <History className="w-5 h-5 text-cyan-400" />
                                <div>
                                    <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">Lịch sử Phiên bản</h3>
                                    <p className="text-[11px] text-slate-400">Chọn một phiên bản để xem lại hoặc đối chiếu nội dung</p>
                                </div>
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
                                versions.map((v: any) => {
                                    const isCurrent = v.version === review?.version;
                                    const isLatest = v.version === Math.max(...versions.map((x: any) => x.version));
                                    const canDelete = !isCurrent && v.status !== 'approved' && !isLatest;
                                    return (
                                        <div
                                            key={v.review_version_id}
                                            onClick={() => handleSelectVersion(v.version)}
                                            className={`p-3 rounded-xl flex items-center justify-between text-xs transition-all cursor-pointer border ${
                                                isCurrent
                                                    ? 'bg-teal-500/10 border-teal-500/40 shadow-sm'
                                                    : 'bg-slate-900/40 border-slate-800 hover:border-teal-500/30 hover:bg-slate-800/60'
                                            }`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${
                                                    isCurrent ? 'bg-teal-500/20 text-teal-300 border border-teal-500/30' : 'bg-slate-800 text-slate-400 border border-slate-700'
                                                }`}>
                                                    v{v.version}
                                                </div>
                                                <div>
                                                    <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                                                        <span>Phiên bản v{v.version}</span>
                                                        {isCurrent && (
                                                            <span className="text-[10px] text-teal-400 font-semibold bg-teal-950/60 px-1.5 py-0.5 rounded border border-teal-500/20">
                                                                Đang hiển thị
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="text-[11px] text-slate-400 mt-0.5">
                                                        {v.created_by || 'Hệ thống'} • {new Date(v.created_at).toLocaleString('vi-VN')}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-2">
                                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                                    v.status === 'approved'
                                                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                                        : isCurrent
                                                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                                            : 'bg-slate-800 text-slate-400 border-slate-700'
                                                }`}>
                                                    {v.status === 'approved' ? 'ĐÃ DUYỆT' : isCurrent ? 'BẢN THẢO' : 'BẢN CŨ'}
                                                </span>
                                                {!isCurrent && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleSelectVersion(v.version);
                                                        }}
                                                        className="px-2.5 py-1 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-[11px] font-bold flex items-center gap-1 shadow-sm transition-all"
                                                    >
                                                        <Eye className="w-3.5 h-3.5" />
                                                        <span>Xem</span>
                                                    </button>
                                                )}
                                                {canDelete && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleDeleteVersion(v.review_version_id, v.version);
                                                        }}
                                                        title="Xóa phiên bản này"
                                                        className="p-1.5 text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded-lg transition-all"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>

                        <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-xs">
                            <span className="text-slate-400 text-[11px]">Click vào bất kỳ bản nào để mở xem.</span>
                            <button
                                onClick={() => {
                                    setShowVersions(false);
                                    loadCurrentReview();
                                }}
                                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg font-semibold text-xs flex items-center gap-1.5 transition-all"
                            >
                                <RotateCcw className="w-3.5 h-3.5 text-teal-400" />
                                <span>Về bản mới nhất</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Custom File Name Export PDF Modal */}
            {showExportModal && (
                <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <div className="clinical-card border border-slate-700 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-in fade-in zoom-in-95 duration-150">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-teal-500/10 flex items-center justify-center border border-teal-500/20 text-teal-400">
                                <Download className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-100 text-sm">Xuất Bệnh án PDF</h3>
                                <p className="text-xs text-slate-400">Đặt tên file tài liệu xuất trước khi tải về</p>
                            </div>
                        </div>

                        <div className="space-y-3 mb-6">
                            <div>
                                <label className="block text-xs font-semibold text-slate-300 mb-1">
                                    Tên file tải về (.pdf):
                                </label>
                                <input
                                    type="text"
                                    value={customExportName}
                                    onChange={(e) => setCustomExportName(e.target.value)}
                                    placeholder="Nhap_ten_file.pdf"
                                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs font-mono text-slate-200 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
                                    autoFocus
                                />
                            </div>
                            <p className="text-[11px] text-slate-500 italic">
                                File sẽ được định dạng chuẩn A4 có đóng dấu điện tử và bảng đối soát lâm sàng.
                            </p>
                        </div>

                        <div className="flex justify-end gap-2.5">
                            <button
                                onClick={() => setShowExportModal(false)}
                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl transition-all cursor-pointer"
                            >
                                Hủy
                            </button>
                            <button
                                onClick={handleExport}
                                className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white text-xs font-bold rounded-xl shadow-lg transition-all cursor-pointer"
                            >
                                <Download className="w-4 h-4" /> Tải xuống PDF
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
