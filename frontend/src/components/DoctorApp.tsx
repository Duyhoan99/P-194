"use client";

import { useState } from "react";

import { DoctorDashboard } from "@/components/DoctorDashboard";
import { PatientWorkspace } from "@/components/PatientWorkspace";
import { ApiError, apiClient } from "@/lib/api";
import type { AssignedPatient, ClinicalSummaryDraft, PatientWorkspace as Workspace, ReviewChecklist } from "@/lib/types";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Please sign in again.";
    if (error.status === 403) return "Access to this subject is denied by the clinical API.";
    if (error.status >= 500) return "Clinical API is unavailable.";
    return error.message;
  }
  return "Clinical API is unavailable.";
}

export function DoctorApp() {
  const [username, setUsername] = useState("doctor-1");
  const [password, setPassword] = useState("demo");
  const [signedIn, setSignedIn] = useState(false);
  const [patients, setPatients] = useState<AssignedPatient[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [denied, setDenied] = useState<string | undefined>();

  async function loadPatients() {
    setLoading(true);
    setError(undefined);
    try {
      setPatients(await apiClient.listPatients());
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoading(false);
    }
  }

  async function login(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(undefined);
    try {
      await apiClient.demoLogin(username, password);
      setSignedIn(true);
      await loadPatients();
    } catch (cause) {
      setError(messageFor(cause));
      setLoading(false);
    }
  }

  async function openWorkspace(subjectId: number) {
    setLoading(true);
    setError(undefined);
    setDenied(undefined);
    try {
      setWorkspace(await apiClient.getPatientWorkspace(subjectId));
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoading(false);
    }
  }

  async function verifyAccess(subjectId: number) {
    setDenied(undefined);
    try {
      await apiClient.getPatientWorkspace(subjectId);
      setDenied("The clinical API granted access; this workspace is server-authorized.");
    } catch (cause) {
      setDenied(cause instanceof ApiError && cause.status === 403 ? `Access to subject ${subjectId} is denied by the clinical API.` : messageFor(cause));
    }
  }

  function setSummary(summary: ClinicalSummaryDraft) {
    setWorkspace((current) => current ? { ...current, summary, patient: { ...current.patient, summaryStatus: summary.status } } : current);
  }

  async function saveSummary(summary: ClinicalSummaryDraft) {
    setSummary(await apiClient.updateSummary(summary.summaryId, summary));
  }

  async function regenerateSummary() {
    if (!workspace) return;
    setSummary(await apiClient.generateSummary(workspace.patient.subjectId));
  }

  async function approveSummary(checklist: ReviewChecklist) {
    if (!workspace?.summary) return;
    setSummary(await apiClient.approveSummary(workspace.summary.summaryId, checklist));
  }

  async function rejectSummary(reason: string) {
    if (!workspace?.summary) return;
    setSummary(await apiClient.rejectSummary(workspace.summary.summaryId, reason));
  }

  async function exportSummary() {
    if (!workspace?.summary) return;
    const pdf = await apiClient.exportSummary(workspace.summary.summaryId);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(pdf);
    link.download = "clinical-summary.pdf";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  if (!signedIn) {
    return (
      <main className="login-page">
        <section className="login-card" aria-labelledby="login-title">
          <p className="eyebrow">Synthetic clinical demo</p>
          <h1 id="login-title">Doctor review interface</h1>
          <p className="disclaimer">Demo authentication creates an HTTP-only server session. Do not use for production care.</p>
          <form onSubmit={login}>
            <label htmlFor="username">Demo username</label>
            <input id="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
            <label htmlFor="password">Demo password</label>
            <input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
            {error && <p className="notice error" role="alert">{error}</p>}
            <button className="primary" type="submit" disabled={loading}>Sign in</button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      {workspace ? (
        <PatientWorkspace
          workspace={workspace}
          reviewerId={username}
          onBack={() => setWorkspace(null)}
          onSave={saveSummary}
          onRegenerate={regenerateSummary}
          onApprove={approveSummary}
          onReject={rejectSummary}
          onExport={exportSummary}
        />
      ) : (
        <DoctorDashboard
          patients={patients}
          loading={loading}
          error={error}
          denied={denied}
          sessionExpired={error === "Your session has expired. Please sign in again."}
          onOpenPatient={(subjectId) => void openWorkspace(subjectId)}
          onVerifyAccess={(subjectId) => void verifyAccess(subjectId)}
        />
      )}
    </main>
  );
}
