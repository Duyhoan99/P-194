"use client";

import { useEffect, useState } from "react";

import { ApiError, apiClient } from "@/lib/api";
import type { ClinicalOperationalStatus, IngestionRun } from "@/lib/types";

function ServiceCard({ title, value }: { title: string; value: string }) {
  return <article className="patient-card"><h2>{title}</h2><p className="status">{value}</p></article>;
}

export default function OperationsPage() {
  const [status, setStatus] = useState<ClinicalOperationalStatus | null>(null);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "denied" | "unavailable">("loading");
  useEffect(() => {
    void Promise.all([apiClient.getClinicalOperationalStatus(), apiClient.listIngestionRuns()]).then(([nextStatus, nextRuns]) => {
      setStatus(nextStatus);
      setRuns(nextRuns);
      setState("ready");
    }).catch((error: unknown) => setState(error instanceof ApiError && error.status === 403 ? "denied" : "unavailable"));
  }, []);

  return <main className="app-shell"><section className="section-heading"><div><p className="eyebrow">Operations</p><h1>Clinical service posture</h1><p className="disclaimer">Operational metadata only; this page never renders clinical records.</p></div></section>
    {state === "loading" && <p className="notice">Loading service status…</p>}
    {state === "denied" && <p className="notice error" role="alert">Permission denied. An administrator or data steward session is required.</p>}
    {state === "unavailable" && <p className="notice error" role="alert">Operational status is unavailable.</p>}
    {state === "ready" && status && <><div className="operational-grid"><ServiceCard title="API" value="AVAILABLE" /><ServiceCard title="Database" value={status.database.status ?? "UNKNOWN"} /><ServiceCard title="Source profile" value={status.sourceProfile} /><ServiceCard title="Ingestion / checksum" value={`${status.ingestion.schema_status} / ${status.ingestion.checksum_status}`} /><ServiceCard title="LLM gateway" value={status.llmGateway.status ?? "UNKNOWN"} /><ServiceCard title="Clinical tools" value={`${status.clinicalTools.status} (${status.clinicalTools.count})`} /></div><section className="summary-section"><h2>Loaded modules</h2><p>{status.loadedModules.join(", ")}</p><h2>Latency budget</h2><p>{status.latency.query_timeout_ms ?? 0} ms query timeout</p></section><section className="summary-section"><h2>Ingestion runs</h2>{runs.map((run) => <dl key={run.runId}><div><dt>Run</dt><dd>{run.runId}</dd></div><div><dt>Dataset/profile</dt><dd>{run.dataset} / {run.profile}</dd></div><div><dt>Checksum/schema</dt><dd>{run.checksumStatus} / {run.schemaStatus}</dd></div><div><dt>Counts</dt><dd>{Object.entries(run.counts).map(([key, value]) => `${key}: ${value}`).join(", ")}</dd></div></dl>)}</section></>}
  </main>;
}
