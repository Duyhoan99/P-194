"use client";

import { useState } from "react";

import { ReviewModal } from "@/components/ReviewModal";
import type { ClinicalSummaryDraft, PatientWorkspace as Workspace, ReviewChecklist } from "@/lib/types";

const tabs = ["Summary", "Timeline", "Medications", "Lab Trends", "Source Records", "Conflicts", "Review History"] as const;

export function PatientWorkspace({
  workspace,
  reviewerId = "doctor-1",
  onSave,
  onApprove,
  onReject,
  onRegenerate,
  onExport,
  onReload,
  onBack,
}: {
  workspace: Workspace;
  reviewerId?: string;
  onSave: (summary: ClinicalSummaryDraft) => Promise<void>;
  onApprove: (checklist: ReviewChecklist) => Promise<void>;
  onReject?: (reason: string) => Promise<void>;
  onRegenerate?: () => Promise<void>;
  onExport?: () => Promise<void>;
  onReload?: () => Promise<void>;
  onBack?: () => void;
}) {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>("Summary");
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [editedClaimTexts, setEditedClaimTexts] = useState<Record<string, string>>({});
  const [reviewNote, setReviewNote] = useState("");
  const [showReview, setShowReview] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const summary = workspace.summary;
  const selectedCitation = summary?.citations.find((citation) => citation.citationId === selectedCitationId);

  async function save() {
    if (!summary) return;
    setError(null);
    try {
      await onSave({
        ...summary,
        sections: Object.fromEntries(
          Object.entries(summary.sections).map(([section, claims]) => [
            section,
            claims.map((claim) => ({ ...claim, text: editedClaimTexts[claim.claimId] ?? claim.text })),
          ]),
        ),
        warnings: reviewNote.trim() ? [...summary.warnings, `Clinician review note: ${reviewNote.trim()}`] : summary.warnings,
      });
      setReviewNote("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The draft could not be saved.");
    }
  }

  async function reject() {
    if (!onReject || !reason.trim()) return;
    setError(null);
    try {
      await onReject(reason.trim());
      setReason("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The draft could not be rejected.");
    }
  }

  async function regenerate() {
    if (!onRegenerate) return;
    setError(null);
    try {
      await onRegenerate();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The summary could not be regenerated.");
    }
  }

  async function exportApproved() {
    if (!onExport) return;
    setError(null);
    try {
      await onExport();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The approved summary could not be exported.");
    }
  }

  return (
    <section aria-labelledby="workspace-title">
      <div className="section-heading">
        <div>
          {onBack && <button type="button" className="link-button" onClick={onBack}>← Assigned patients</button>}
          <p className="eyebrow">Subject {workspace.patient.subjectId}</p>
          <h1 id="workspace-title">Patient workspace</h1>
        </div>
        <span className={`status status-${summary?.status ?? "NOT_STARTED"}`}>{summary?.status ?? "NOT_STARTED"}</span>
      </div>
      <p className="disclaimer">Decision support only. This interface does not make clinical decisions.</p>
      {workspace.availability !== "AVAILABLE" && <p className="notice warning">Some source data is {workspace.availability.toLowerCase()}.</p>}
      {workspace.warnings.map((warning) => <p className="notice warning" key={warning}>{warning}</p>)}
      {workspace.evidencePages.some(({ page }) => page.hasMore) && (
        <div className="notice warning" role="alert">
          Evidence is truncated; reload to request the continuation.
          {onReload && <button type="button" onClick={() => void onReload()}>Reload workspace</button>}
        </div>
      )}
      {workspace.limitations.map((limitation) => <p className="notice" key={limitation}>{limitation}</p>)}
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="tabs" role="tablist" aria-label="Clinical workspace sections">
        {tabs.map((tab) => <button key={tab} type="button" role="tab" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}
      </div>
      {activeTab === "Summary" && (
        <div className="workspace-grid">
          <div>
            {!summary ? (
              <>
                <p>No current summary is available for this server-authorized workspace.</p>
                {onRegenerate && <button type="button" className="primary" onClick={() => void regenerate()}>Generate draft</button>}
              </>
            ) : (
              <>
                {Object.entries(summary.sections).map(([section, claims]) => claims.length > 0 && (
                  <section className="summary-section" key={section}>
                    <h2>{section}</h2>
                    {claims.map((claim) => (
                      <div key={claim.claimId}>
                        <label className="sr-only" htmlFor={`claim-${claim.claimId}`}>Edit {claim.claimId}</label>
                        <textarea
                          id={`claim-${claim.claimId}`}
                          value={editedClaimTexts[claim.claimId] ?? claim.text}
                          onChange={(event) => setEditedClaimTexts((current) => ({ ...current, [claim.claimId]: event.target.value }))}
                        />
                        {claim.citationIds.map((citationId) => (
                          <button className="citation" type="button" key={citationId} onClick={() => setSelectedCitationId(citationId)}>{citationId}</button>
                        ))}
                      </div>
                    ))}
                  </section>
                ))}
                <section className="summary-section">
                  <h2>Conflicts and missing information</h2>
                  <ConflictList summary={summary} />
                </section>
              </>
            )}
          </div>
          {selectedCitationId && (
            <aside className="source-panel" aria-label="Source record">
              <h2>Source record</h2>
              {selectedCitation ? (
                <dl>
                  <div><dt>Source</dt><dd>{selectedCitation.lineage.table}</dd></div>
                  <div><dt>Record</dt><dd>{selectedCitation.citationId}</dd></div>
                  <div><dt>Supported fields</dt><dd>{selectedCitation.supportedFields.join(", ") || "Unavailable"}</dd></div>
                </dl>
              ) : <p className="notice warning">Citation unavailable.</p>}
              <button type="button" onClick={() => setSelectedCitationId(null)}>Close source</button>
            </aside>
          )}
        </div>
      )}
      {activeTab === "Timeline" && <RecordList records={workspace.timeline} empty="No timeline records are available." />}
      {activeTab === "Medications" && <ClaimList claims={summary?.sections["Current and Recent Medications"] ?? []} empty="No medication claims are available." />}
      {activeTab === "Lab Trends" && <ClaimList claims={summary?.sections["Laboratory Trends"] ?? []} empty="No laboratory claims are available." />}
      {activeTab === "Source Records" && <RecordList records={workspace.sourceRecords ?? []} empty="No source records are available." />}
      {activeTab === "Conflicts" && <ConflictList summary={summary} />}
      {activeTab === "Review History" && <p>Review history is maintained by the server as immutable summary versions.</p>}
      {summary && summary.status !== "APPROVED" && summary.status !== "EXPORTED" && (
        <section className="review-actions" aria-labelledby="review-actions-title">
          <h2 id="review-actions-title">Review actions</h2>
          <label htmlFor="review-note">Review note (citation tokens are preserved)</label>
          <textarea id="review-note" value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} />
          <div className="action-row">
            <button type="button" onClick={save}>Revalidate and save draft</button>
            {onRegenerate && <button type="button" onClick={() => void regenerate()}>Request regeneration</button>}
            <button type="button" onClick={() => setShowReview(true)}>Approve</button>
          </div>
          {onReject && <div className="reject-row"><input aria-label="Rejection reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason for rejection" /><button type="button" onClick={reject} disabled={!reason.trim()}>Reject</button></div>}
        </section>
      )}
      {summary && (summary.status === "APPROVED" || summary.status === "EXPORTED") && onExport && <button type="button" className="primary" onClick={() => void exportApproved()}>Export approved PDF</button>}
      {showReview && summary && <ReviewModal summary={summary} reviewerId={reviewerId} onApprove={onApprove} onClose={() => setShowReview(false)} />}
    </section>
  );
}

function ClaimList({ claims, empty }: { claims: ClinicalSummaryDraft["sections"][string]; empty: string }) {
  return claims.length ? <ul>{claims.map((claim) => <li key={claim.claimId}>{claim.text}</li>)}</ul> : <p>{empty}</p>;
}

function RecordList({ records, empty }: { records: NonNullable<Workspace["sourceRecords"]>; empty: string }) {
  return records.length ? <ul>{records.map((record) => <li key={`${record.lineage.table}:${record.lineage.sourceRowKey}`}>{record.recordType} — {record.lineage.table}</li>)}</ul> : <p>{empty}</p>;
}

function ConflictList({ summary }: { summary: ClinicalSummaryDraft | null }) {
  if (!summary?.conflicts.length) return <p>No conflicts were returned by the server.</p>;
  return <ul>{summary.conflicts.map((conflict) => <li key={conflict.conflictId}>{conflict.topic} — {conflict.status}</li>)}</ul>;
}
