"use client";

import { useMemo, useState } from "react";

import type { AssignedPatient } from "@/lib/types";

export function DoctorDashboard({
  patients,
  loading = false,
  error,
  denied,
  sessionExpired = false,
  onOpenPatient,
  onVerifyAccess,
}: {
  patients: AssignedPatient[];
  loading?: boolean;
  error?: string;
  denied?: string;
  sessionExpired?: boolean;
  onOpenPatient: (subjectId: number) => void;
  onVerifyAccess?: (subjectId: number) => void;
}) {
  const [query, setQuery] = useState("");
  const [subjectToVerify, setSubjectToVerify] = useState("");
  const matchingPatients = useMemo(
    () => patients.filter((patient) => String(patient.subjectId).includes(query.trim())),
    [patients, query],
  );

  if (loading) return <p role="status">Loading assigned patients…</p>;
  if (sessionExpired) return <div className="notice warning" role="alert">Your session has expired. Please sign in again.</div>;
  if (error) return <div className="notice error" role="alert">{error}</div>;

  return (
    <section aria-labelledby="assigned-patients-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Clinical review workspace</p>
          <h1 id="assigned-patients-title">Assigned patients</h1>
        </div>
        <p className="disclaimer">De-identified demo data. Decision support only.</p>
      </div>
      {denied && <div className="notice warning" role="alert">{denied}</div>}
      <label className="search-label" htmlFor="patient-search">Search assigned patients</label>
      <input id="patient-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Subject ID" />
      {patients.length === 0 ? (
        <p>No patients are currently assigned to this session.</p>
      ) : matchingPatients.length === 0 ? (
        <p>No assigned patients match this search.</p>
      ) : (
        <div className="patient-grid">
          {matchingPatients.map((patient) => (
            <article className="patient-card" key={patient.subjectId}>
              <h2>Subject {patient.subjectId}</h2>
              <dl>
                <div><dt>Anchor age</dt><dd>{patient.anchorAge ?? "Unavailable"}</dd></div>
                <div><dt>Sex</dt><dd>{patient.gender}</dd></div>
                <div><dt>Admissions</dt><dd>{patient.admissionCount}</dd></div>
                <div><dt>ICU stays</dt><dd>{patient.icuStayCount}</dd></div>
                <div><dt>Summary</dt><dd>{patient.summaryStatus}</dd></div>
              </dl>
              <button type="button" className="primary" onClick={() => onOpenPatient(patient.subjectId)}>Open workspace</button>
            </article>
          ))}
        </div>
      )}
      {onVerifyAccess && (
        <form className="access-check" onSubmit={(event) => { event.preventDefault(); if (/^\d+$/.test(subjectToVerify)) onVerifyAccess(Number(subjectToVerify)); }}>
          <label htmlFor="verify-subject">Verify server access for a subject ID</label>
          <input id="verify-subject" inputMode="numeric" value={subjectToVerify} onChange={(event) => setSubjectToVerify(event.target.value)} />
          <button type="submit">Check access</button>
        </form>
      )}
    </section>
  );
}
