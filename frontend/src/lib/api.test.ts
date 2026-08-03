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

function clinicalResponse(
  page: { has_more: boolean; next_cursor: string | null },
  sourceRowKey = "labevent_id=9001",
) {
  return {
    status: "SUCCESS",
    records: [{ record_type: "lab", data: { label: "Creatinine" }, lineage: { ...lineage, source_row_key: sourceRowKey } }],
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

it("requests stored continuation cursors and merges continuation records safely", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: true, next_cursor: "cursor-2" }, "overview-first")))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null }, "timeline-first")))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null }, "labs-first")))
    .mockResolvedValueOnce(jsonResponse(summaryVersion("DRAFT")))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null }, "overview-next")))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null }, "timeline-reloaded")))
    .mockResolvedValueOnce(jsonResponse(clinicalResponse({ has_more: false, next_cursor: null }, "labs-reloaded")))
    .mockResolvedValueOnce(jsonResponse(summaryVersion("DRAFT")));
  vi.stubGlobal("fetch", fetchMock);

  const firstPage = await apiClient.getPatientWorkspace(101);
  const continued = await apiClient.getPatientWorkspace(101, {
    cursors: { overview: firstPage.evidencePages[0].page.nextCursor },
    previous: firstPage,
  });

  expect(fetchMock.mock.calls[4][0]).toContain("/api/v1/clinical/patients/101?cursor=cursor-2");
  expect(fetchMock.mock.calls[5][0]).toBe("http://localhost:8000/api/v1/clinical/patients/101/timeline");
  expect(continued.evidenceRecordsBySource.overview.map((record) => record.lineage.sourceRowKey)).toEqual([
    "overview-first",
    "overview-next",
  ]);
  expect(continued.evidencePages[0]).toEqual({ source: "overview", page: { hasMore: false, nextCursor: null } });
  expect(continued.availability).toBe("AVAILABLE");
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
