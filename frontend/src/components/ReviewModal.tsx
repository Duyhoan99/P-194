"use client";

import { useState } from "react";

import type { ClinicalSummaryDraft, ReviewChecklist } from "@/lib/types";

const checklistLabels: Array<[keyof ReviewChecklist, string]> = [
  ["reviewedSummary", "I reviewed the summary"],
  ["checkedCriticalEvidence", "I checked critical evidence"],
  ["understandsAiLimitations", "I understand AI is decision support only"],
  ["confirmsEdits", "I confirm my edits"],
];

export function ReviewModal({
  summary,
  reviewerId,
  onApprove,
  onClose,
}: {
  summary: ClinicalSummaryDraft;
  reviewerId: string;
  onApprove: (checklist: ReviewChecklist) => Promise<void>;
  onClose: () => void;
}) {
  const [checklist, setChecklist] = useState<ReviewChecklist>({
    reviewedSummary: false,
    checkedCriticalEvidence: false,
    understandsAiLimitations: false,
    confirmsEdits: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unresolvedConflicts = summary.conflicts.filter((conflict) => conflict.status === "UNRESOLVED");
  const claims = Object.values(summary.sections).flat();
  const citationIds = new Set(summary.citations.map((citation) => citation.citationId));
  const invalidClaims = claims.filter((claim) => claim.status !== "VALID");
  const missingCitations = claims
    .filter((claim) => claim.status === "VALID")
    .flatMap((claim) => claim.citationIds.filter((citationId) => !citationIds.has(citationId)));
  const hasCitationErrors = invalidClaims.length > 0 || missingCitations.length > 0;
  const eligible = Object.values(checklist).every(Boolean) && unresolvedConflicts.length === 0 && !hasCitationErrors;

  async function approve() {
    if (!eligible) return;
    setSubmitting(true);
    setError(null);
    try {
      await onApprove(checklist);
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Approval could not be completed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" aria-modal="true" role="dialog" aria-labelledby="review-title">
        <h2 id="review-title">Approve clinical summary</h2>
        <p>Reviewer: <strong>{reviewerId}</strong></p>
        <p className="disclaimer">Decision support only. Confirm source evidence before using this summary.</p>
        {unresolvedConflicts.length > 0 && (
          <div className="notice warning" role="alert">
            <strong>Unresolved conflicts block approval.</strong>
            <ul>{unresolvedConflicts.map((conflict) => <li key={conflict.conflictId}>{conflict.topic}</li>)}</ul>
          </div>
        )}
        {hasCitationErrors && <div className="notice error" role="alert">Citation validation errors block approval.</div>}
        <fieldset>
          <legend>Required review checklist</legend>
          {checklistLabels.map(([key, label]) => (
            <label className="check-row" key={key}>
              <input
                type="checkbox"
                checked={checklist[key]}
                onChange={(event) => setChecklist((current) => ({ ...current, [key]: event.target.checked }))}
              />
              {label}
            </label>
          ))}
        </fieldset>
        {error && <p className="notice error" role="alert">{error}</p>}
        <div className="action-row">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="primary" disabled={!eligible || submitting} onClick={approve}>Approve</button>
        </div>
      </section>
    </div>
  );
}
