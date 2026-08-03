"use client";

import { useMemo, useState } from "react";

import type { AuditMetadata } from "@/lib/types";

export function AuditTable({ events }: { events: AuditMetadata[] }) {
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [result, setResult] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const visibleEvents = useMemo(() => events.filter((event) => (
    (!actor || event.actor === actor)
    && (!action || event.action === action)
    && (!result || event.result === result)
    && (!fromDate || event.timestamp >= `${fromDate}T00:00:00`)
    && (!toDate || event.timestamp <= `${toDate}T23:59:59.999Z`)
  )), [action, actor, events, fromDate, result, toDate]);
  const actors = [...new Set(events.map((event) => event.actor))];
  const actions = [...new Set(events.map((event) => event.action))];
  const results = [...new Set(events.map((event) => event.result))];

  return (
    <section className="audit-table" aria-label="Append-only audit history">
      <div className="audit-filters">
        <label>Actor<select aria-label="Actor" value={actor} onChange={(event) => setActor(event.target.value)}><option value="">All actors</option>{actors.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>Action<select aria-label="Action" value={action} onChange={(event) => setAction(event.target.value)}><option value="">All actions</option>{actions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>Result<select aria-label="Result" value={result} onChange={(event) => setResult(event.target.value)}><option value="">All results</option>{results.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>From<input aria-label="From" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label>
        <label>To<input aria-label="To" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label>
      </div>
      {visibleEvents.length === 0 ? <p className="notice">No audit metadata matches these filters.</p> : (
        <table>
          <thead><tr><th>Actor</th><th>Action</th><th>Subject reference</th><th>Result</th><th>Time</th><th>Trace ID</th></tr></thead>
          <tbody>{visibleEvents.map((event) => <tr key={`${event.traceId}-${event.action}`}><td>{event.actor}</td><td>{event.action}</td><td>{event.subjectReference}</td><td>{event.result}</td><td>{new Date(event.timestamp).toLocaleString()}</td><td>{event.traceId}</td></tr>)}</tbody>
        </table>
      )}
    </section>
  );
}
