"use client";

import { useEffect, useState } from "react";

import { AuditTable } from "@/components/AuditTable";
import { ApiError, apiClient } from "@/lib/api";
import type { AuditMetadata } from "@/lib/types";

export default function ComplianceAuditPage() {
  const [events, setEvents] = useState<AuditMetadata[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "denied" | "unavailable">("loading");
  useEffect(() => {
    void apiClient.listAuditEvents().then((nextEvents) => {
      setEvents(nextEvents);
      setState("ready");
    }).catch((error: unknown) => setState(error instanceof ApiError && error.status === 403 ? "denied" : "unavailable"));
  }, []);

  return <main className="app-shell"><section className="section-heading"><div><p className="eyebrow">Compliance</p><h1>Append-only audit metadata</h1><p className="disclaimer">This view excludes clinical values, prompts, request headers, and secrets.</p></div></section>
    {state === "loading" && <p className="notice">Loading audit metadata…</p>}
    {state === "denied" && <p className="notice error" role="alert">Permission denied. A compliance or administrator session is required.</p>}
    {state === "unavailable" && <p className="notice error" role="alert">Audit metadata is unavailable.</p>}
    {state === "ready" && <AuditTable events={events} />}
  </main>;
}
