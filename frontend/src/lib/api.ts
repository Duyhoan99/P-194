/* API Client for Clinical Backend */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const API_V1 = `${API_BASE}/api/v1`;

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | undefined | null>;
}

export class ApiError extends Error {
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
    let detail = 'Unknown error';
    let trace_id: string | undefined;
    try {
      const err = await res.json();
      if (err.detail) {
        detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      }
      trace_id = err.trace_id;
    } catch {
      /* ignore */
    }
    // If 401 and we are in browser, might want to redirect to login or clear state
    if (res.status === 401 && typeof window !== 'undefined' && window.location.pathname !== '/login') {
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
    
  ask: (patient_id: string, question: string) =>
    request<any>(`/patients/${patient_id}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question })
    }),

  generateReview: (patient_id: string, profile_versions: string[]) =>
    request<any>(`/patients/${patient_id}/reviews/generate`, {
      method: 'POST',
      body: JSON.stringify({ profile_versions })
    }),

  getReview: (patient_id: string, version?: number) =>
    request<any>(`/patients/${patient_id}/review`, { params: { version } }),

  getTimeline: (patient_id: string, page: number = 1, page_size: number = 50) =>
    request<any>(`/patients/${patient_id}/timeline`, { params: { page, page_size } }),

  getTrends: (patient_id: string, code: string) =>
    request<any>(`/patients/${patient_id}/trends`, { params: { code } }),

  getDrugInteractions: (patient_id: string) =>
    request<any>(`/patients/${patient_id}/drug-interactions`),
};

/* ========== Ingestions ========== */
export const ingestions = {
  upload: (file: File, patient_id?: string, format: string = 'auto', new_patient_name?: string) => {
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

  reject: (patient_id: string, review_id: string, expected_version: number, reason: string) => 
    request<any>(`/reviews/${review_id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ expected_version, reason })
    }),

  exportPdf: async (patient_id: string, review_id: string, review_version_id: string) => {
    const res = await fetch(`${API_V1}/reviews/${review_id}/export.pdf?review_version_id=${encodeURIComponent(review_version_id)}`, {
      method: 'GET',
      credentials: 'include',
    });
    if (!res.ok) throw new ApiError(res.status, 'Export failed');
    return res.blob();
  },

  listVersions: (review_id: string, page: number = 1) =>
    request<any>(`/reviews/${review_id}/versions`, { params: { page } }),
};
