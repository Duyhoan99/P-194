/* API Client for Clinical Backend */

// Same-origin requests are the safe default: Next proxies /api to the backend,
// so browser cookies work without a second CORS origin and remote demo users do
// not accidentally call port 8000 on their own machine.
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
const API_V1 = `${API_BASE}/api/v1`;


interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | undefined | null>;
}

export interface CarePlanDraft {
  doctor_greeting: string;
  personalization_summary: string;
  medication_need: 'yes' | 'no' | 'undetermined';
  medication_assessment: string;
  medication_recommendation: string;
  medication_basis_ids: string[];
  morning_meds: string;
  evening_meds: string;
  medication_note: string;
  diet_good: string;
  diet_bad: string;
  diet_basis_ids: string[];
  exercise: string;
  exercise_basis_ids: string[];
  emergency_warning: string;
  warning_basis_ids: string[];
  follow_up: string;
  follow_up_days: number | null;
  guideline_citation: string;
}

export interface ClinicalBasisItem {
  basis_id: string;
  source_title: string;
  source_reference: string;
  section: string;
  applied_content: string;
  applies_to: Array<'medication' | 'diet' | 'exercise' | 'warning'>;
}

export interface CarePlanDataSummary {
  conditions: string[];
  medications: string[];
  latest_observations: string[];
  allergies: string[];
  conflicts: string[];
}

export interface CarePlanResponse {
  status: 'draft' | 'needs_review';
  generation_mode: 'deterministic_grounded' | 'llm_grounded';
  agent_type: string;
  data_watermark: string;
  requires_clinician_review: boolean;
  disclaimer: string;
  safety_flags: string[];
  guideline_citations: string[];
  evidence_citation_ids: string[];
  clinical_basis: ClinicalBasisItem[];
  data_summary: CarePlanDataSummary;
  plan: CarePlanDraft;
}

export interface CarePlanPdfExportRequest {
  plan: CarePlanDraft;
  data_summary: CarePlanDataSummary;
  doctor_sign_name: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  trace_id?: string;

  constructor(status: number, detail: any, trace_id?: string) {
    const message = typeof detail === 'string'
      ? detail
      : (detail && typeof detail === 'object' && detail.message)
        ? String(detail.message)
        : JSON.stringify(detail || 'Unknown error');
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = message;
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

  const isFormData = fetchOptions.body instanceof FormData;

  const headers = new Headers(fetchOptions.headers);
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(url, {
    ...fetchOptions,
    headers,
    credentials: 'include',
  });

  if (!res.ok) {
    let detail: any = 'Unknown error';
    let trace_id: string | undefined;
    try {
      const err = await res.json();
      if (err.detail !== undefined) {
        detail = err.detail;
      }
      trace_id = err.trace_id || (typeof err.detail === 'object' ? err.detail?.trace_id : undefined);
    } catch {
      /* ignore */
    }
    // If 401 and we are in browser, might want to redirect to login or clear state
    if (res.status === 401 && typeof window !== 'undefined' && window.location.pathname !== '/login') {
        // The transport layer cannot use a React router hook. A full navigation
        // also clears any stale client state after the server rejects the session.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = '/login';
    }
    throw new ApiError(res.status, detail, trace_id);
  }

  if (res.status === 204 || res.status === 202) {
    // some 202s return JSON, try to parse
    try {
        const text = await res.text();
        return text ? JSON.parse(text) : (undefined as T);
    } catch {
        return undefined as T;
    }
  }

  return res.json();
}

/* ========== Auth ========== */
export const auth = {
  login: (email: string, password: string) =>
    request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    request<void>('/auth/logout', { method: 'POST' }),

  me: () => 
    request<any>('/auth/me', { method: 'GET' })
};

/* ========== Patients ========== */
export const patients = {
  list: (params?: { page?: number; page_size?: number; search?: string }) =>
    request<any>('/patients', { method: 'GET', params }),

  get: (patientId: string) =>
    request<any>(`/patients/${patientId}`),
    
  delete: (patientId: string) =>
    request<any>(`/patients/${patientId}`, { method: 'DELETE' }),

  getMemory: (patient_id: string) => 
    request<any>(`/patients/${patient_id}/memory`),
    
  getChatHistory: (patient_id: string, session_id: string) =>
    request<{ messages: { role: 'user' | 'assistant', text: string }[] }>(`/patients/${patient_id}/ask/history?session_id=${session_id}`),

  getSessions: (patient_id: string) =>
    request<{ id: string; patient_id: string; title: string; created_at: string; updated_at: string }[]>(`/patients/${patient_id}/ask/sessions`),

  renameSession: (patient_id: string, session_id: string, title: string) =>
    request<any>(`/patients/${patient_id}/ask/sessions/${session_id}`, {
      method: 'PUT',
      body: JSON.stringify({ title })
    }),

  deleteSession: (patient_id: string, session_id: string) =>
    request<any>(`/patients/${patient_id}/ask/sessions/${session_id}`, { method: 'DELETE' }),
    
  ask: (patient_id: string, question: string, session_id?: string) =>
    request<any>(`/patients/${patient_id}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, session_id })
    }),

  generateReview: (patient_id: string, profile_versions: string[]) =>
    request<any>(`/patients/${patient_id}/reviews/generate`, {
      method: 'POST',
      body: JSON.stringify({ profile_versions })
    }),

  getReview: (patient_id: string, version?: number) =>
    request<any>(`/patients/${patient_id}/review`, {
      params: { version, allow_missing: 'true' },
    }),

  getTimeline: (patient_id: string, page: number = 1, page_size: number = 50) =>
    request<any>(`/patients/${patient_id}/timeline`, { params: { page, page_size } }),

  getTrends: (patient_id: string, code: string) =>
    request<any>(`/patients/${patient_id}/trends`, { params: { code } }),

  getDrugInteractions: (patient_id: string) =>
    request<any>(`/patients/${patient_id}/drug-interactions`),

  generateCarePlan: (patient_id: string) =>
    request<CarePlanResponse>(`/patients/${patient_id}/care-plan`, { method: 'POST' }),

  exportCarePlanPdf: async (patient_id: string, payload: CarePlanPdfExportRequest) => {
    const res = await fetch(`${API_V1}/patients/${patient_id}/care-plan/export.pdf`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let detail: any = `Không thể xuất PDF hướng dẫn điều trị (mã lỗi ${res.status}).`;
      try {
        const errorPayload = await res.json();
        detail = errorPayload.detail ?? errorPayload.message ?? detail;
      } catch {
        // Keep the Vietnamese fallback for non-JSON server errors.
      }
      throw new ApiError(res.status, detail);
    }

    const contentType = res.headers.get('content-type') || '';
    if (!contentType.toLowerCase().includes('application/pdf')) {
      throw new ApiError(502, 'Máy chủ trả về dữ liệu không phải file PDF.');
    }
    const blob = await res.blob();
    if (blob.size === 0) {
      throw new ApiError(502, 'File PDF được tạo nhưng không có nội dung.');
    }
    return blob;
  },
};

/* ========== Ingestions ========== */
export const ingestions = {
  upload: (file: File, patient_id?: string, new_patient_name?: string, format: string = 'auto') => {
    const formData = new FormData();
    formData.append('file', file);
    if (patient_id) formData.append('patient_id', patient_id);
    if (new_patient_name) formData.append('new_patient_name', new_patient_name);
    formData.append('format', format);

    return request<any>('/ingestions', {
      method: 'POST',
      body: formData,
      headers: {
        'Idempotency-Key': `upload-${Date.now()}-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`
      }
    });
  },

  getStatus: (batch_id: string) =>
    request<any>(`/ingestions/${batch_id}`),

  list: (limit: number = 10) =>
    request<any[]>(`/ingestions?limit=${limit}`),

  getQuota: () =>
    request<{used_bytes: number, total_bytes: number}>('/ingestions/quota')
};

/* ========== Reviews ========== */
export const reviews = {
  edit: (patient_id: string, review_id: string, expected_version: number, sections: any[], edit_reason: string) => 
    request<any>(`/reviews/${review_id}`, {
      method: 'PATCH',
      body: JSON.stringify({ expected_version, sections, edit_reason })
    }),
    
  approve: (patient_id: string, review_id: string, review_version_id: string, expected_version: number, clinician_confirmation: boolean = true) => 
    request<any>(`/reviews/${review_id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ review_version_id, expected_version, clinician_confirmation })
    }),

  reject: (patient_id: string, review_id: string, expected_version: number, reason: string, review_version_id?: string) => 
    request<any>(`/reviews/${review_id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ review_version_id, expected_version, reason })
    }),

  exportPdf: async (patient_id: string, review_id: string, review_version_id: string) => {
    const res = await fetch(`${API_V1}/reviews/${review_id}/export.pdf?review_version_id=${encodeURIComponent(review_version_id)}`, {
      method: 'GET',
      credentials: 'include',
    });
    if (!res.ok) {
      let detail: any = `Không thể xuất PDF (mã lỗi ${res.status}).`;
      try {
        const payload = await res.json();
        detail = payload.detail ?? payload.message ?? detail;
      } catch {
        // Keep the Vietnamese fallback for non-JSON server errors.
      }
      throw new ApiError(res.status, detail);
    }

    const contentType = res.headers.get('content-type') || '';
    if (!contentType.toLowerCase().includes('application/pdf')) {
      throw new ApiError(502, 'Máy chủ trả về dữ liệu không phải file PDF.');
    }

    const blob = await res.blob();
    if (blob.size === 0) {
      throw new ApiError(502, 'File PDF được tạo nhưng không có nội dung.');
    }
    return blob;
  },

  listVersions: (review_id: string, page: number = 1) =>
    request<any>(`/reviews/${review_id}/versions`, { params: { page } }),
};

/* ========== Admin Types & API ========== */
export interface UserResponse {
  user_id: string;
  username?: string;
  role: 'ADMIN' | 'DOCTOR' | 'NURSE' | 'REVIEWER' | string;
  state?: string;
  assignments: string[];
  created_at?: string;
}

export interface AuditEntry {
  id?: string;
  event_type?: string;
  actor: string;
  action: string;
  patient_id?: string;
  result: string;
  trace_id: string;
  timestamp: string;
  details?: Record<string, any>;
}

export const admin = {
  listUsers: () => request<{ users: UserResponse[] }>('/admin/users'),
  listAudit: () => request<{ events: AuditEntry[] }>('/admin/audit'),
  grantAssignment: (user_id: string, patient_id: string) =>
    request<any>(`/admin/users/${encodeURIComponent(user_id)}/assignments`, {
      method: 'POST',
      body: JSON.stringify({ patient_id })
    }),
  revokeAssignment: (user_id: string, patient_id: string) =>
    request<any>(`/admin/users/${encodeURIComponent(user_id)}/assignments/${encodeURIComponent(patient_id)}`, {
      method: 'DELETE'
    }),
};
