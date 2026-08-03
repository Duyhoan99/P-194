export type SummaryStatus = "DRAFT" | "NEEDS_REVISION" | "REJECTED" | "APPROVED" | "EXPORTED";
export type PatientSummaryStatus = SummaryStatus | "UNAVAILABLE";
export type Availability = "AVAILABLE" | "PARTIAL" | "NOT_LOADED";

export interface EvidencePage {
  nextCursor: string | null;
  hasMore: boolean;
}

export type EvidenceSource = "overview" | "timeline" | "labs";

export interface EvidenceResponse {
  status: "SUCCESS" | "PARTIAL" | "EMPTY" | "DENIED" | "NOT_LOADED";
  records: EvidenceRecord[];
  warnings: string[];
  limitations: string[];
  traceId: string;
  page: EvidencePage;
}

export interface EvidencePageState {
  source: EvidenceSource;
  page: EvidencePage;
}

export type WorkspaceCursors = Partial<Record<EvidenceSource, string | null>>;

export interface AssignedPatient {
  subjectId: number;
  anchorAge: number | null;
  gender: string;
  admissionCount: number;
  icuStayCount: number;
  summaryStatus: PatientSummaryStatus;
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
  evidencePages: EvidencePageState[];
  evidenceRecordsBySource: Record<EvidenceSource, EvidenceRecord[]>;
  sourceRecords?: EvidenceRecord[];
}

export interface WorkspaceLoadOptions {
  cursors?: WorkspaceCursors;
  previous?: PatientWorkspace;
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

export interface AssignmentHistoryEntry {
  subjectReference: string;
  action: "ASSIGN_CLINICAL_SUBJECT" | "REVOKE_CLINICAL_SUBJECT";
  actor: string;
  timestamp: string;
}

export interface OperationalUser {
  userId: string;
  role: "DOCTOR" | "ADMIN" | "DATA_STEWARD" | "COMPLIANCE";
  state: "ACTIVE" | "LOCKED";
  assignments: string[];
  assignmentHistory: AssignmentHistoryEntry[];
}

export interface AuditMetadata {
  actor: string;
  action: string;
  subjectReference: string;
  timestamp: string;
  result: "SUCCESS" | "PARTIAL" | "EMPTY" | "DENIED" | "NOT_LOADED" | "ERROR";
  traceId: string;
}

export interface ClinicalOperationalStatus {
  backend: string;
  database: Record<string, string>;
  loadedModules: string[];
  sourceProfile: string;
  ingestion: Record<string, string>;
  llmGateway: Record<string, string>;
  clinicalTools: { status: string; count: number };
  latency: Record<string, number>;
  traceId: string;
}

export interface IngestionRun {
  runId: string;
  dataset: string;
  profile: string;
  checksumStatus: string;
  schemaStatus: string;
  counts: Record<string, number>;
  errors: string[];
}
