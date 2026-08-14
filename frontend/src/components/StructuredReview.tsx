'use client';

import { useState, useEffect, useCallback } from 'react';
import { reviews, patients, ApiError } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { FileSignature, CheckCircle, XCircle, Clock, AlertTriangle, Download, RefreshCw, Edit3, Save, X, History, ShieldCheck, Ban } from 'lucide-react';

export default function StructuredReview({ patientId }: { patientId: string }) {
    const [review, setReview] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const { setFocusedCitation, setCurrentReview } = useAppStore();

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

    // First try to load existing review, then fall back to generate
    const loadCurrentReview = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const res = await patients.getReview(patientId);
            setReview(res);
            setCurrentReview(res);
        } catch {
            // No existing review found — that's OK, user can generate one
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
            setError(err.detail || 'Failed to generate review');
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
            setError(err.detail || 'Edit failed');
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
            setError('Cannot approve: some claims need verification first.');
            setShowApproveConfirm(false);
            return;
        }

        // Check stale
        if (review.status === 'stale') {
            setError('Cannot approve a stale review. Please regenerate.');
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
            setError(err.detail || 'Approval failed');
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
            setError(err.detail || 'Rejection failed');
        }
    };

    // ---- Export ----
    const handleExport = async () => {
        if (!review) return;
        if (review.status !== 'approved') {
            setError('Export only available for approved reviews.');
            return;
        }
        try {
            const blob = await reviews.exportPdf(patientId, review.review_id, review.review_version_id);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Clinical_Review_${patientId}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (err: any) {
            setError(err.detail || 'Export failed');
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

    // ---- Render States ----
    if (loading && !review) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-slate-400">
                <RefreshCw className="w-8 h-8 animate-spin mb-4 text-cyan-500" />
                <p className="text-sm">Loading clinical review...</p>
            </div>
        );
    }

    if (error && !review) {
        return (
            <div className="p-6 bg-red-950/20 border border-red-900/50 rounded-xl flex flex-col items-center">
                <AlertTriangle className="w-8 h-8 text-red-500 mb-2" />
                <p className="text-sm text-red-400 text-center">{error}</p>
                <button onClick={loadCurrentReview} className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-md text-sm">Retry</button>
            </div>
        );
    }

    if (!review) {
        return (
            <div className="flex flex-col items-center justify-center p-12 bg-slate-900/40 backdrop-blur-xl border border-slate-700/50 rounded-2xl h-full shadow-2xl shadow-cyan-900/10">
                <div className="w-20 h-20 rounded-full bg-slate-800/50 flex items-center justify-center mb-6 shadow-inner shadow-cyan-500/10 border border-slate-700/50">
                    <FileSignature className="w-10 h-10 text-cyan-500/50" />
                </div>
                <h3 className="text-lg font-bold text-slate-200 mb-2">No Clinical Review Found</h3>
                <p className="text-sm text-slate-400 mb-8 max-w-sm text-center">Analyze the patient&apos;s medical records and generate a structured clinical summary based on uploaded evidence.</p>
                <button
                    onClick={generateReview}
                    disabled={loading}
                    className="px-8 py-3.5 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg shadow-cyan-900/40 hover:shadow-cyan-500/30 ring-1 ring-white/10 transition-all duration-300 transform hover:-translate-y-0.5 disabled:opacity-50"
                >
                    {loading ? 'Generating...' : 'Generate Clinical Review'}
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
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
        : isStale
            ? 'bg-red-500/10 text-red-400 border-red-500/20'
            : isRejected
                ? 'bg-orange-500/10 text-orange-400 border-orange-500/20'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/20';

    return (
        <div className="bg-slate-900 border border-slate-700/50 rounded-2xl shadow-xl overflow-hidden flex flex-col h-full min-h-[500px]">
            {/* Header */}
            <div className="p-4 border-b border-slate-800 bg-slate-950/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <FileSignature className="w-5 h-5 text-cyan-500" />
                    <div>
                        <h3 className="text-sm font-bold text-slate-100">Structured Review</h3>
                        <div className="flex items-center gap-2 mt-0.5 text-xs">
                            <span className={`px-2 py-0.5 rounded-full font-medium border ${statusColor}`}>
                                {review.status.toUpperCase()}
                            </span>
                            <span className="text-slate-500 font-mono">v{review.version}</span>
                            {review.is_current_watermark === false && (
                                <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-bold">
                                    STALE DATA
                                </span>
                            )}
                        </div>
                    </div>
                </div>
                <div className="flex gap-2 items-center">
                    {error && <span className="text-xs text-red-400 mr-2 max-w-[200px] truncate">{error}</span>}

                    {/* Version History */}
                    <button
                        onClick={loadVersions}
                        className="p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-slate-800 transition-colors"
                        title="Version History"
                    >
                        <History className="w-4 h-4" />
                    </button>

                    {/* Reject */}
                    {canApprove && (
                        <button
                            onClick={() => setShowRejectModal(true)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-red-900/30 border border-slate-700 hover:border-red-800 text-slate-300 hover:text-red-400 text-xs font-medium rounded-md transition-all"
                        >
                            <Ban className="w-3.5 h-3.5" /> Reject
                        </button>
                    )}

                    {/* Approve */}
                    {canApprove && (
                        <button
                            onClick={() => setShowApproveConfirm(true)}
                            className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-md transition-colors shadow-sm"
                        >
                            <CheckCircle className="w-3.5 h-3.5" /> Approve
                        </button>
                    )}

                    {/* Export */}
                    {isApproved && (
                        <button
                            onClick={handleExport}
                            className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white text-xs font-medium rounded-md transition-colors"
                        >
                            <Download className="w-3.5 h-3.5" /> Export PDF
                        </button>
                    )}

                    {/* Regenerate */}
                    <button
                        onClick={generateReview}
                        className="p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-slate-800 transition-colors"
                        title="Regenerate Review"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Disclaimer */}
            {review.disclaimer && (
                <div className="px-5 py-2 bg-slate-950/80 border-b border-slate-800/50 flex items-center gap-2">
                    <ShieldCheck className="w-3.5 h-3.5 text-cyan-500/50 shrink-0" />
                    <p className="text-[10px] text-slate-500 leading-relaxed">{review.disclaimer}</p>
                </div>
            )}

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-5 space-y-8">
                {sections.map((section: any, idx: number) => (
                    <div
                        key={section.section_code || idx}
                        className="space-y-3"
                    >
                        <h4 className="text-sm font-semibold text-cyan-500 uppercase tracking-wider flex items-center gap-2">
                            {section.title || section.section_code?.replace(/_/g, ' ')}
                        </h4>
                        <div className="space-y-2">
                            {section.claims && section.claims.length > 0 ? (
                                section.claims.map((claim: any) => (
                                    <div key={claim.claim_id} className="p-3 bg-slate-950/30 border border-slate-800/60 rounded-lg text-sm text-slate-300 leading-relaxed hover:bg-slate-800/30 transition-colors group relative">
                                        {editingClaim === claim.claim_id ? (
                                            /* --- EDIT MODE --- */
                                            <div className="space-y-3">
                                                <textarea
                                                    value={editText}
                                                    onChange={(e) => setEditText(e.target.value)}
                                                    className="w-full bg-slate-900 border border-cyan-800/50 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 min-h-[80px] resize-y"
                                                />
                                                <input
                                                    type="text"
                                                    value={editReason}
                                                    onChange={(e) => setEditReason(e.target.value)}
                                                    placeholder="Reason for edit (required)..."
                                                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
                                                />
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={saveEdit}
                                                        disabled={!editReason.trim()}
                                                        className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium rounded-md disabled:opacity-50 transition-colors"
                                                    >
                                                        <Save className="w-3 h-3" /> Save
                                                    </button>
                                                    <button
                                                        onClick={cancelEditing}
                                                        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-md transition-colors"
                                                    >
                                                        <X className="w-3 h-3" /> Cancel
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            /* --- VIEW MODE --- */
                                            <>
                                                <span>{claim.text}</span>
                                                {claim.citations && claim.citations.length > 0 && (
                                                    <span className="inline-flex gap-1 ml-2 align-middle">
                                                        {claim.citations.map((cit: any) => (
                                                            <button
                                                                key={cit.citation_id || Math.random()}
                                                                onClick={() => handleCitationClick(cit)}
                                                                className="inline-flex items-center justify-center min-w-[20px] h-[20px] px-1 text-[10px] font-bold font-mono bg-slate-800 hover:bg-cyan-900 text-cyan-400 border border-slate-700 hover:border-cyan-500 rounded cursor-pointer transition-all shadow-sm group-hover:shadow-cyan-900/20"
                                                                title="View evidence"
                                                            >
                                                                {cit.citation_id?.split('-').pop()?.substring(0, 4) || '*'}
                                                            </button>
                                                        ))}
                                                    </span>
                                                )}
                                                {claim.status === 'needs_verification' && (
                                                    <span className="inline-flex items-center gap-1 ml-2 text-[10px] uppercase font-bold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                                                        <AlertTriangle className="w-3 h-3" /> Verify
                                                    </span>
                                                )}
                                                {claim.status === 'unsupported' && (
                                                    <span className="inline-flex items-center gap-1 ml-2 text-[10px] uppercase font-bold text-red-500 bg-red-500/10 px-1.5 py-0.5 rounded border border-red-500/20">
                                                        <XCircle className="w-3 h-3" /> Unsupported
                                                    </span>
                                                )}
                                                {/* Edit button */}
                                                {canEdit && (
                                                    <button
                                                        onClick={() => startEditing(claim.claim_id, claim.text)}
                                                        className="absolute top-2 right-2 p-1 opacity-0 group-hover:opacity-100 text-slate-500 hover:text-cyan-400 rounded transition-all hover:bg-slate-800"
                                                        title="Edit claim"
                                                    >
                                                        <Edit3 className="w-3.5 h-3.5" />
                                                    </button>
                                                )}
                                            </>
                                        )}
                                    </div>
                                ))
                            ) : (
                                <p className="text-sm text-slate-500 italic">No information available.</p>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* Approve Confirmation Modal */}
            {showApproveConfirm && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-100">Confirm Approval</h3>
                                <p className="text-xs text-slate-400">This action saves the review to patient memory</p>
                            </div>
                        </div>
                        <p className="text-sm text-slate-300 mb-6">
                            By approving, you confirm that you have reviewed all clinical facts and their evidence citations. This review will become the official clinical record.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowApproveConfirm(false)}
                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleApprove}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors shadow-lg shadow-emerald-900/30"
                            >
                                ✓ I confirm and approve
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
                            <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center border border-red-500/20">
                                <Ban className="w-5 h-5 text-red-400" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-100">Reject Review</h3>
                                <p className="text-xs text-slate-400">Please provide a reason for rejection</p>
                            </div>
                        </div>
                        <textarea
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="Explain why this review is being rejected (min 3 characters)..."
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-red-500 min-h-[100px] resize-y mb-4"
                        />
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => { setShowRejectModal(false); setRejectReason(''); }}
                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleReject}
                                disabled={rejectReason.trim().length < 3}
                                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors shadow-lg shadow-red-900/30 disabled:opacity-50"
                            >
                                Reject Review
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Version History Modal */}
            {showVersions && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-lg w-full mx-4 shadow-2xl max-h-[70vh] flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="font-bold text-slate-100 flex items-center gap-2">
                                <History className="w-4 h-4 text-cyan-400" /> Version History
                            </h3>
                            <button onClick={() => setShowVersions(false)} className="p-1 text-slate-400 hover:text-white rounded">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto space-y-2">
                            {versionsLoading ? (
                                <div className="text-center py-8 text-slate-500 text-sm">Loading versions...</div>
                            ) : versions.length === 0 ? (
                                <div className="text-center py-8 text-slate-500 text-sm">No version history available.</div>
                            ) : (
                                versions.map((v: any, idx: number) => (
                                    <div key={v.review_version_id || idx} className="p-3 bg-slate-800/30 border border-slate-700/50 rounded-lg flex items-center justify-between">
                                        <div>
                                            <div className="text-sm text-slate-200 font-medium">Version {v.version}</div>
                                            <div className="text-xs text-slate-500 mt-0.5">
                                                {v.status?.toUpperCase()} • {v.updated_at ? new Date(v.updated_at).toLocaleString() : 'Unknown'}
                                            </div>
                                            {v.edit_reason && (
                                                <div className="text-xs text-slate-400 mt-1 italic">&quot;{v.edit_reason}&quot;</div>
                                            )}
                                        </div>
                                        <span className="text-[10px] font-mono text-slate-600 truncate max-w-[100px]">{v.review_version_id}</span>
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
