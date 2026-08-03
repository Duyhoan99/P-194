import { apiClient } from "@/lib/api";

const traceId = "trace-api-test";
const lineage = {
  dataset: "synthetic-demo",
  version: "1",
  module: "hosp" as const,
  table: "labevents",
  source_row_key: "labevent_id=9001",
  subject_id: 101,
};

function clinicalResponse(page: { has_more: boolean; next_cursor: string | null }) {
  return {
    status: "SUCCESS",
    records: [{ record_type: "lab", data: { label: "Creatinine" }, lineage }],
    warnings: [],
    limitations: [],
    trace_id: traceId,
    page,
  };
}

function summaryVersion(status: "DRAFT" | "APPROVED") {
  return {
    status,
    version_id: "version-1",
    version_number: status === "DRAFT" ? 1 : 2,
    summary_id: "summary-1",
    actor_id: "doctor-1",
    reason: null,
    created_at: "2026-08-03T00:00:00Z",
    draft: {
      summary_id: "summary-1",
      subject_id: 101,
      status,
      sections: {},
      citations: [],
      conflicts: [],
      warnings: [],
      limitations: [],
      trace_id: traceId,
    },
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => vi.restoreAllMocks());

it("preserves page metadata and marks a successful but truncated workspace partial", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: true, next_cursor: "cursor-2" })))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse(summaryVersion("DRAFT"))));

  const workspace = await apiClient.getPatientWorkspace(101);

  expect(workspace.availability).toBe("PARTIAL");
  expect(workspace.evidencePages[0]).toEqual({ source: "overview", page: { hasMore: true, nextCursor: "cursor-2" } });
  expect(workspace.warnings).toContain("Evidence is truncated; reload to request the continuation.");
});

it("loads the server-owned current summary status for an assigned patient", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse(summaryVersion("APPROVED"))));

  const workspace = await apiClient.getPatientWorkspace(101);

  expect(workspace.summary?.status).toBe("APPROVED");
  expect(workspace.patient.summaryStatus).toBe("APPROVED");
});

it("represents an absent current summary as unavailable rather than not started", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null })))
    .mockResolvedValueOnce(jsonResponse({ detail: "Summary not found." }, 404)));

  const workspace = await apiClient.getPatientWorkspace(101);

  expect(workspace.summary).toBeNull();
  expect(workspace.patient.summaryStatus).toBe("UNAVAILABLE");
});
