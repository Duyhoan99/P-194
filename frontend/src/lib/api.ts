/* API Client for Clinical Backend */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const API_V1 = `${API_BASE}/api/v1`;

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | undefined | null>;
}

class ApiError extends Error {
  status: number;
  detail: string;
  trace_id?: string;

  constructor(status: number, detail: string, trace_id?: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.trace_id = trace_id;
  }
}

async function request<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;

  let url = `${API_V1}${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.set(key, String(value));
      }
    });
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }

  const res = await fetch(url, {
    ...fetchOptions,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...fetchOptions.headers,
    },
  });

  if (!res.ok) {
    let detail = 'Unknown error';
    let trace_id: string | undefined;
    try {
      const err = await res.json();
      detail = err.detail || detail;
      trace_id = err.trace_id;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail, trace_id);
  }

  if (res.status === 204) return undefined as T;

  return res.json();
}

/* ========== Auth ========== */
export const auth = {
  login: (username: string, password: string) =>
    request<void>('/auth/demo-login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  logout: () =>
    request<void>('/auth/logout', { method: 'POST' }),
};

/* ========== Clinical ========== */
export interface ClinicalRecord {
  record_type: string;
  data: Record<string, unknown>;
  lineage: {
    dataset: string;
    version: string;
    module: string;
    table: string;
    source_row_key: string;
    subject_id: number;
    hadm_id?: number;
    stay_id?: number;
    event_time?: string;
  };
  related_sources: unknown[];
}

export interface ClinicalResponse {
  status: string;
  records: ClinicalRecord[];
  warnings: string[];
  limitations: string[];
  trace_id: string;
  page: {
    next_cursor?: string;
    has_more: boolean;
  };
}

export interface AssignedPatientsResponse {
  patients: number[];
  trace_id: string;
}

interface ClinicalQueryParams {
  hadm_id?: number;
  stay_id?: number;
  from_time?: string;
  to_time?: string;
  limit?: number;
  cursor?: string;
}

export const clinical = {
  getAssignedPatients: () =>
    request<AssignedPatientsResponse>('/clinical/patients'),

  getPatientOverview: (subjectId: number, params?: ClinicalQueryParams) =>
    request<ClinicalResponse>(`/clinical/patients/${subjectId}`, { params: params as Record<string, string | number | undefined> }),

  getTimeline: (subjectId: number, params?: ClinicalQueryParams) =>
    request<ClinicalResponse>(`/clinical/patients/${subjectId}/timeline`, { params: params as Record<string, string | number | undefined> }),

  getDiagnosesProcedures: (subjectId: number, params?: ClinicalQueryParams) =>
    request<ClinicalResponse>(`/clinical/patients/${subjectId}/diagnoses-procedures`, { params: params as Record<string, string | number | undefined> }),

  getLabs: (subjectId: number, params?: ClinicalQueryParams) =>
    request<ClinicalResponse>(`/clinical/patients/${subjectId}/labs`, { params: params as Record<string, string | number | undefined> }),

  getMicrobiology: (subjectId: number, params?: ClinicalQueryParams) =>
    request<ClinicalResponse>(`/clinical/patients/${subjectId}/microbiology`, { params: params as Record<string, string | number | undefined> }),

  getMedications: (subjectId: number, params?: ClinicalQueryParams) =>
    request<ClinicalResponse>(`/clinical/patients/${subjectId}/medications`, { params: params as Record<string, string | number | undefined> }),

  getIcuEvents: (subjectId: number, params?: ClinicalQueryParams) =>
    request<ClinicalResponse>(`/clinical/patients/${subjectId}/icu-events`, { params: params as Record<string, string | number | undefined> }),
};

/* ========== Summaries ========== */
export interface Claim {
  claim_id: string;
  section: string;
  text: string;
  citation_ids: string[];
  status: string;
}

export interface Citation {
  citation_id: string;
  lineage: ClinicalRecord['lineage'];
  supported_fields: string[];
}

export interface Conflict {
  conflict_id: string;
  topic: string;
  evidence_ids: string[];
  status: string;
  resolution_note?: string;
  resolved_by?: string;
}

export interface ClinicalSummaryDraft {
  summary_id: string;
  subject_id: number;
  hadm_id?: number;
  stay_id?: number;
  status: string;
  sections: Record<string, Claim[]>;
  citations: Citation[];
  conflicts: Conflict[];
  warnings: string[];
  limitations: string[];
  trace_id: string;
}

export interface SummaryVersion {
  summary_id: string;
  version_number: number;
  status: string;
  draft: ClinicalSummaryDraft;
  actor_id: string;
  created_at: string;
  reason?: string;
}

export const summaries = {
  getCurrent: (subjectId: number) =>
    request<SummaryVersion>(`/clinical/patients/${subjectId}/summaries/current`),

  generate: (subjectId: number, hadmId?: number, stayId?: number) =>
    request<SummaryVersion>(`/clinical/patients/${subjectId}/summaries`, {
      method: 'POST',
      body: JSON.stringify({ hadm_id: hadmId, stay_id: stayId }),
    }),

  get: (summaryId: string) =>
    request<SummaryVersion>(`/clinical/summaries/${summaryId}`),

  edit: (summaryId: string, draft: ClinicalSummaryDraft, reason?: string) =>
    request<SummaryVersion>(`/clinical/summaries/${summaryId}`, {
      method: 'PATCH',
      body: JSON.stringify({ draft, reason }),
    }),

  listVersions: (summaryId: string) =>
    request<SummaryVersion[]>(`/clinical/summaries/${summaryId}/versions`),

  approve: (summaryId: string, checklist: {
    reviewed_summary: boolean;
    checked_critical_evidence: boolean;
    understands_ai_limitations: boolean;
    confirms_edits: boolean;
  }) =>
    request<SummaryVersion>(`/clinical/summaries/${summaryId}/approve`, {
      method: 'POST',
      body: JSON.stringify(checklist),
    }),

  reject: (summaryId: string, reason: string) =>
    request<SummaryVersion>(`/clinical/summaries/${summaryId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  exportPdf: async (summaryId: string) => {
    const res = await fetch(`${API_V1}/clinical/summaries/${summaryId}/export`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!res.ok) throw new ApiError(res.status, 'Export failed');
    return res.blob();
  },
};

/* ========== Chat ========== */
export interface ChatResponse {
  response: string;
  analysis: string;
}

export const chat = {
  send: (message: string) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
};

/* ========== Admin ========== */
export interface UserResponse {
  user_id: string;
  role: string;
  state: string;
  assignments: string[];
  assignment_history: {
    subject_reference: string;
    action: string;
    actor: string;
    timestamp: string;
  }[];
}

export interface AuditEntry {
  actor: string;
  action: string;
  subject_reference: string;
  timestamp: string;
  result: string;
  trace_id: string;
}

export const admin = {
  listUsers: () =>
    request<{ users: UserResponse[]; trace_id: string }>('/admin/users'),

  grantAssignment: (userId: string, subjectId: number) =>
    request<UserResponse>(`/admin/users/${userId}/assignments`, {
      method: 'POST',
      body: JSON.stringify({ subject_id: subjectId }),
    }),

  revokeAssignment: (userId: string, subjectId: number) =>
    request<UserResponse>(`/admin/users/${userId}/assignments/${subjectId}`, {
      method: 'DELETE',
    }),

  listAudit: (params?: {
    actor?: string;
    action?: string;
    result?: string;
    from_time?: string;
    to_time?: string;
  }) =>
    request<{ events: AuditEntry[]; trace_id: string }>('/admin/audit', {
      params: params as Record<string, string | undefined>,
    }),
};

/* ========== Ops ========== */
export const ops = {
  getStatus: () =>
    request<{ backend: string; database: Record<string, string>; loaded_modules: string[] }>('/ops/clinical-status'),
};

/* ========== Agent Status ========== */
export const agent = {
  status: () =>
    request<{ status: string; agent: string }>('/status'),
};

/* ========== Health ========== */
export const health = {
  check: () =>
    fetch(`/health`, { credentials: 'include' }).then(r => r.json()),
};

export { ApiError };
