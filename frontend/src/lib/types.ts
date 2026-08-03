export type SummaryStatus = "DRAFT" | "NEEDS_REVISION" | "REJECTED" | "APPROVED" | "EXPORTED";
export type Availability = "AVAILABLE" | "PARTIAL" | "NOT_LOADED";

export interface AssignedPatient {
  subjectId: number;
  anchorAge: number | null;
  gender: string;
  admissionCount: number;
  icuStayCount: number;
  summaryStatus: SummaryStatus | "NOT_STARTED";
}

export interface SourceLineage {
  dataset: string;
  version: string;
  module: "hosp" | "icu";
  table: string;
  sourceRowKey: string;
  subjectId: number;
  hadmId?: number | null;
  stayId?: number | null;
  eventTime?: string | null;
}

export interface Citation {
  citationId: string;
  lineage: SourceLineage;
  supportedFields: string[];
}

export interface Claim {
  claimId: string;
  section: string;
  text: string;
  citationIds: string[];
  status: "VALID" | "INVALID" | "UNSUPPORTED";
}

export interface SummaryConflict {
  conflictId: string;
  topic: string;
  evidenceIds: string[];
  status: "UNRESOLVED" | "RESOLVED";
  resolutionNote: string | null;
  resolvedBy?: string | null;
}

export interface ClinicalSummaryDraft {
  summaryId: string;
  subjectId: number;
  hadmId?: number | null;
  stayId?: number | null;
  status: SummaryStatus;
  sections: Record<string, Claim[]>;
  citations: Citation[];
  conflicts: SummaryConflict[];
  warnings: string[];
  limitations: string[];
  traceId: string;
}

export interface EvidenceRecord {
  recordType: string;
  data: Record<string, unknown>;
  lineage: SourceLineage;
}

export interface PatientWorkspace {
  patient: AssignedPatient;
  availability: Availability;
  timeline: EvidenceRecord[];
  summary: ClinicalSummaryDraft | null;
  warnings: string[];
  limitations: string[];
  sourceRecords?: EvidenceRecord[];
}

export interface SummaryScope {
  hadmId?: number;
  stayId?: number;
}

export interface ReviewChecklist {
  reviewedSummary: boolean;
  checkedCriticalEvidence: boolean;
  understandsAiLimitations: boolean;
  confirmsEdits: boolean;
}
