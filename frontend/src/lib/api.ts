import type {
  AssignedPatient,
  ClinicalSummaryDraft,
  EvidenceRecord,
  PatientWorkspace,
  ReviewChecklist,
  SourceLineage,
  SummaryScope,
} from "@/lib/types";

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly traceId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RawRecord = {
  record_type: string;
  data: Record<string, unknown>;
  lineage: RawLineage;
};

type RawLineage = {
  dataset: string;
  version: string;
  module: "hosp" | "icu";
  table: string;
  source_row_key: string;
  subject_id: number;
  hadm_id?: number | null;
  stay_id?: number | null;
  event_time?: string | null;
};

type RawClinicalResponse = {
  status: "SUCCESS" | "PARTIAL" | "NOT_LOADED";
  records: RawRecord[];
  warnings?: string[];
  limitations?: string[];
};

type RawSummaryVersion = {
  status: ClinicalSummaryDraft["status"];
  draft: RawDraft;
};

type RawDraft = {
  summary_id: string;
  subject_id: number;
  hadm_id?: number | null;
  stay_id?: number | null;
  status: ClinicalSummaryDraft["status"];
  sections: Record<string, Array<{ claim_id: string; section: string; text: string; citation_ids: string[]; status: "VALID" | "INVALID" | "UNSUPPORTED" }>>;
  citations: Array<{ citation_id: string; lineage: RawLineage; supported_fields: string[] }>;
  conflicts: Array<{ conflict_id: string; topic: string; evidence_ids: string[]; status: "UNRESOLVED" | "RESOLVED"; resolution_note: string | null; resolved_by?: string | null }>;
  warnings?: string[];
  limitations: string[];
  trace_id: string;
};

function fromLineage(lineage: RawLineage): SourceLineage {
  return {
    dataset: lineage.dataset,
    version: lineage.version,
    module: lineage.module,
    table: lineage.table,
    sourceRowKey: lineage.source_row_key,
    subjectId: lineage.subject_id,
    hadmId: lineage.hadm_id,
    stayId: lineage.stay_id,
    eventTime: lineage.event_time,
  };
}

function fromRecord(record: RawRecord): EvidenceRecord {
  return { recordType: record.record_type, data: record.data, lineage: fromLineage(record.lineage) };
}

function fromDraft(draft: RawDraft): ClinicalSummaryDraft {
  return {
    summaryId: draft.summary_id,
    subjectId: draft.subject_id,
    hadmId: draft.hadm_id,
    stayId: draft.stay_id,
    status: draft.status,
    sections: Object.fromEntries(
      Object.entries(draft.sections).map(([section, claims]) => [
        section,
        claims.map((claim) => ({
          claimId: claim.claim_id,
          section: claim.section,
          text: claim.text,
          citationIds: claim.citation_ids,
          status: claim.status,
        })),
      ]),
    ),
    citations: draft.citations.map((citation) => ({
      citationId: citation.citation_id,
      lineage: fromLineage(citation.lineage),
      supportedFields: citation.supported_fields,
    })),
    conflicts: draft.conflicts.map((conflict) => ({
      conflictId: conflict.conflict_id,
      topic: conflict.topic,
      evidenceIds: conflict.evidence_ids,
      status: conflict.status,
      resolutionNote: conflict.resolution_note,
      resolvedBy: conflict.resolved_by,
    })),
    warnings: draft.warnings ?? [],
    limitations: draft.limitations,
    traceId: draft.trace_id,
  };
}

function toRawDraft(draft: ClinicalSummaryDraft): RawDraft {
  return {
    summary_id: draft.summaryId,
    subject_id: draft.subjectId,
    hadm_id: draft.hadmId,
    stay_id: draft.stayId,
    status: draft.status,
    sections: Object.fromEntries(
      Object.entries(draft.sections).map(([section, claims]) => [
        section,
        claims.map((claim) => ({
          claim_id: claim.claimId,
          section: claim.section,
          text: claim.text,
          citation_ids: claim.citationIds,
          status: claim.status,
        })),
      ]),
    ),
    citations: draft.citations.map((citation) => ({
      citation_id: citation.citationId,
      lineage: {
        dataset: citation.lineage.dataset,
        version: citation.lineage.version,
        module: citation.lineage.module,
        table: citation.lineage.table,
        source_row_key: citation.lineage.sourceRowKey,
        subject_id: citation.lineage.subjectId,
        hadm_id: citation.lineage.hadmId,
        stay_id: citation.lineage.stayId,
        event_time: citation.lineage.eventTime,
      },
      supported_fields: citation.supportedFields,
    })),
    conflicts: draft.conflicts.map((conflict) => ({
      conflict_id: conflict.conflictId,
      topic: conflict.topic,
      evidence_ids: conflict.evidenceIds,
      status: conflict.status,
      resolution_note: conflict.resolutionNote,
      resolved_by: conflict.resolvedBy,
    })),
    warnings: draft.warnings,
    limitations: draft.limitations,
    trace_id: draft.traceId,
  };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => ({}))) as { detail?: string; trace_id?: string } & T;
  if (!response.ok) {
    throw new ApiError(response.status, body.detail ?? "Clinical API request failed.", body.trace_id);
  }
  return body;
}

function unique(values: string[][]): string[] {
  return [...new Set(values.flat())];
}

function patientFromResponses(subjectId: number, overview: RawClinicalResponse, timeline: RawClinicalResponse): AssignedPatient {
  const patient = overview.records.find((record) => record.record_type === "patient")?.data;
  return {
    subjectId,
    anchorAge: typeof patient?.anchor_age === "number" ? patient.anchor_age : null,
    gender: typeof patient?.gender === "string" ? patient.gender : "Unknown",
    admissionCount: overview.records.filter((record) => record.record_type === "admission").length,
    icuStayCount: timeline.records.filter((record) => record.record_type === "icu_stay").length,
    summaryStatus: "NOT_STARTED",
  };
}

async function clinicalResponse(path: string): Promise<RawClinicalResponse> {
  return request<RawClinicalResponse>(path);
}

export const apiClient = {
  async demoLogin(username: string, password: string): Promise<void> {
    await request<void>("/api/v1/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  async listPatients(): Promise<AssignedPatient[]> {
    const assigned = await request<{ patients: number[] }>("/api/v1/clinical/patients");
    return Promise.all(assigned.patients.map(async (subjectId) => (await this.getPatientWorkspace(subjectId)).patient));
  },

  async getPatientWorkspace(subjectId: number): Promise<PatientWorkspace> {
    const [overview, timeline, labs] = await Promise.all([
      clinicalResponse(`/api/v1/clinical/patients/${subjectId}`),
      clinicalResponse(`/api/v1/clinical/patients/${subjectId}/timeline`),
      clinicalResponse(`/api/v1/clinical/patients/${subjectId}/labs`),
    ]);
    const responses = [overview, timeline, labs];
    const availability = responses.some((response) => response.status === "PARTIAL")
      ? "PARTIAL"
      : responses.some((response) => response.status === "NOT_LOADED")
        ? "NOT_LOADED"
        : "AVAILABLE";
    return {
      patient: patientFromResponses(subjectId, overview, timeline),
      availability,
      timeline: timeline.records.map(fromRecord),
      summary: null,
      warnings: unique(responses.map((response) => response.warnings ?? [])),
      limitations: unique(responses.map((response) => response.limitations ?? [])),
      sourceRecords: responses.flatMap((response) => response.records.map(fromRecord)),
    };
  },

  async generateSummary(subjectId: number, scope: SummaryScope = {}): Promise<ClinicalSummaryDraft> {
    const version = await request<RawSummaryVersion>(`/api/v1/clinical/patients/${subjectId}/summaries`, {
      method: "POST",
      body: JSON.stringify({ hadm_id: scope.hadmId, stay_id: scope.stayId }),
    });
    return fromDraft(version.draft);
  },

  async updateSummary(summaryId: string, patch: ClinicalSummaryDraft): Promise<ClinicalSummaryDraft> {
    const version = await request<RawSummaryVersion>(`/api/v1/clinical/summaries/${summaryId}`, {
      method: "PATCH",
      body: JSON.stringify({ draft: toRawDraft(patch), reason: "Clinician saved review note." }),
    });
    return fromDraft(version.draft);
  },

  async approveSummary(summaryId: string, checklist: ReviewChecklist): Promise<ClinicalSummaryDraft> {
    const version = await request<RawSummaryVersion>(`/api/v1/clinical/summaries/${summaryId}/approve`, {
      method: "POST",
      body: JSON.stringify({
        reviewed_summary: checklist.reviewedSummary,
        checked_critical_evidence: checklist.checkedCriticalEvidence,
        understands_ai_limitations: checklist.understandsAiLimitations,
        confirms_edits: checklist.confirmsEdits,
      }),
    });
    return fromDraft(version.draft);
  },

  async rejectSummary(summaryId: string, reason: string): Promise<ClinicalSummaryDraft> {
    const version = await request<RawSummaryVersion>(`/api/v1/clinical/summaries/${summaryId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    return fromDraft(version.draft);
  },

  async exportSummary(summaryId: string): Promise<Blob> {
    const response = await fetch(`${apiBaseUrl}/api/v1/clinical/summaries/${summaryId}/export`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { detail?: string; trace_id?: string };
      throw new ApiError(response.status, body.detail ?? "Clinical export failed.", body.trace_id);
    }
    return response.blob();
  },
};
