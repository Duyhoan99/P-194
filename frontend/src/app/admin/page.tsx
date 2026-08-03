"use client";

import { useEffect, useState } from "react";

import { ApiError, apiClient } from "@/lib/api";
import type { OperationalUser } from "@/lib/types";

function stateFor(error: unknown): "denied" | "unavailable" {
  return error instanceof ApiError && error.status === 403 ? "denied" : "unavailable";
}

export default function AdminPage() {
  const [users, setUsers] = useState<OperationalUser[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "denied" | "unavailable">("loading");

  useEffect(() => {
    void apiClient.listOperationalUsers().then((nextUsers) => {
      setUsers(nextUsers);
      setState("ready");
    }).catch((error: unknown) => setState(stateFor(error)));
  }, []);

  return <main className="app-shell"><section className="section-heading"><div><p className="eyebrow">Administration</p><h1>Operational accounts</h1><p className="disclaimer">Account and assignment metadata only. Clinical content cannot be changed here.</p></div></section>
    {state === "loading" && <p className="notice">Loading operational accounts…</p>}
    {state === "denied" && <p className="notice error" role="alert">Permission denied. An administrator session is required.</p>}
    {state === "unavailable" && <p className="notice error" role="alert">Administrative data is unavailable.</p>}
    {state === "ready" && <div className="operational-grid">{users.map((user) => <article className="patient-card" key={user.userId}><h2>{user.userId}</h2><dl><div><dt>Role</dt><dd>{user.role}</dd></div><div><dt>State</dt><dd>{user.state}</dd></div><div><dt>Assignments</dt><dd>{user.assignments.join(", ") || "None"}</dd></div></dl><h3>Assignment history</h3>{user.assignmentHistory.length === 0 ? <p>None recorded.</p> : <ul>{user.assignmentHistory.map((entry) => <li key={`${entry.action}-${entry.timestamp}`}>{entry.action}: {entry.subjectReference}</li>)}</ul>}</article>)}</div>}
  </main>;
}
