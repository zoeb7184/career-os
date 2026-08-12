/**
 * lib/api.ts
 * ───────────
 * Typed fetch client for the Career OS backend (FastAPI @ localhost:8000).
 *
 * Every backend response follows the same envelope:
 *   { "data": <result>, "error": null }
 *   { "data": null, "error": { "code": "...", "message": "...", "detail": {} } }
 *
 * `apiFetch` unwraps that envelope and throws `ApiError` on failure, so
 * call sites can just `await` and try/catch (or let a caller-level toast
 * handle it).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  code: string;
  detail: Record<string, unknown>;
  status: number;

  constructor(code: string, message: string, detail: Record<string, unknown>, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.detail = detail;
    this.status = status;
  }
}

interface Envelope<T> {
  data: T | null;
  error: { code: string; message: string; detail: Record<string, unknown> } | null;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("career-os-auth");
    if (!raw) return null;
    return JSON.parse(raw)?.state?.token ?? null;
  } catch {
    return null;
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit & { auth?: boolean; isForm?: boolean } = {}
): Promise<T> {
  const { auth = false, isForm = false, headers, ...rest } = options;
  const finalHeaders: Record<string, string> = { ...(headers as Record<string, string>) };

  if (!isForm) finalHeaders["Content-Type"] = "application/json";

  if (auth) {
    const token = getToken();
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...rest, headers: finalHeaders });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Could not reach the Career OS API. Is the backend running?", {}, 0);
  }

  let body: Envelope<T> | null = null;
  try {
    body = await res.json();
  } catch {
    // non-JSON response (rare — usually a proxy/500 with HTML)
  }

  if (!res.ok || body?.error) {
    const err = body?.error;
    throw new ApiError(
      err?.code ?? `HTTP_${res.status}`,
      err?.message ?? `Request failed with status ${res.status}`,
      err?.detail ?? {},
      res.status
    );
  }

  return body!.data as T;
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

// ── Types ────────────────────────────────────────────────────────────

export interface AuthResponse {
  token: string;
  user_id: string;
  email: string;
}

export interface User {
  id: string;
  email: string;
}

export interface JobSummary {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  country: string | null;
  remote_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  posted_at: string | null;
  source: string;
}

export interface JobDetail extends Omit<JobSummary, "source"> {
  description: string | null;
  source: string;
  url: string | null;
  required_skills: string[];
  preferred_skills: string[];
}

export interface JobListResponse {
  total: number;
  page: number;
  limit: number;
  pages: number;
  jobs: JobSummary[];
}

export interface ATSResult {
  overall_score: number;
  breakdown: {
    skill_match: number;
    embedding_sim: number;
    structural: number;
    keyword: number;
  };
  missing_skills: string[];
  matched_skills: string[];
  suggestions: string[];
  processing_ms: number;
  resume_id: string | null;
  job_id: string | null;
}

export interface Recommendation {
  job_id: string;
  title: string;
  company: string | null;
  location: string | null;
  remote_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  posted_at: string | null;
  url: string | null;
  final_score: number;
  matched_skills: string[];
}

export interface RecommendResponse {
  user_id: string;
  total_candidates: number;
  returned: number;
  filters: Record<string, unknown>;
  recommendations: Recommendation[];
}

export interface AdvisorResponse {
  answer: string;
  intent: string;
  sources: string[];
  job_count: number;
}

export interface TopSkill {
  skill: string;
  category: string | null;
  job_count: number;
  avg_salary_max: number | null;
}

export interface RemoteBreakdown {
  remote_type: string;
  count: number;
  percentage: number;
}

export interface TopCompany {
  company: string;
  open_roles: number;
  avg_salary: number | null;
}

export interface TopLocation {
  location: string;
  country: string | null;
  job_count: number;
}

export interface SalaryBySkill {
  skill: string;
  salary_min: number | null;
  salary_avg: number | null;
  salary_max: number | null;
  job_count: number;
  country: string | null;
}

export interface DashboardSummary {
  total_active_jobs: number;
  total_companies: number;
  total_countries: number;
  remote_jobs: number;
  new_today: number;
}

export interface SkillForecast {
  skill_name: string;
  current_demand: number;
  forecast_30d: number;
  forecast_60d: number;
  forecast_90d: number;
  trend: "growing" | "stable" | "declining";
  confidence_low: number;
  confidence_high: number;
  data_points: number;
}

export interface ResumeSummary {
  id: string;
  filename: string;
  uploaded_at: string | null;
}

export type ApplicationStatus = "saved" | "applied" | "interview" | "offer" | "rejected";

export interface Application {
  id: string;
  job_id: string;
  status: ApplicationStatus;
  ats_score: number | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
  job: {
    title: string | null;
    company: string | null;
    location: string | null;
    remote_type: string | null;
  };
}

// ── Auth ─────────────────────────────────────────────────────────────

export const auth = {
  register: (email: string, password: string) =>
    apiFetch<AuthResponse>(`${API_PREFIX}/auth/register`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    apiFetch<AuthResponse>(`${API_PREFIX}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => apiFetch<User>(`${API_PREFIX}/auth/me`, { auth: true }),
};

// ── Jobs ─────────────────────────────────────────────────────────────

export const jobs = {
  list: (params: {
    q?: string;
    country?: string;
    remote_type?: string;
    skill?: string;
    salary_min?: number;
    page?: number;
    limit?: number;
  }) => apiFetch<JobListResponse>(`${API_PREFIX}/jobs${qs(params)}`),
  get: (id: string) => apiFetch<JobDetail>(`${API_PREFIX}/jobs/${id}`),
};

// ── ATS ──────────────────────────────────────────────────────────────

export const ats = {
  analyze: (file: File, jobId: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("job_id", jobId);
    return apiFetch<ATSResult>(`${API_PREFIX}/ats/analyze`, {
      method: "POST",
      body: form,
      isForm: true,
    });
  },
};

// ── Recommend ────────────────────────────────────────────────────────

export const recommend = {
  forUser: (
    userId: string,
    params: { top_n?: number; country?: string; remote_type?: string; salary_min?: number } = {}
  ) => apiFetch<RecommendResponse>(`${API_PREFIX}/recommend/${userId}${qs(params)}`, { auth: true }),
};

// ── Advisor ──────────────────────────────────────────────────────────

export const advisor = {
  ask: (question: string, userId: string, userSkills?: string[], resumeSummary?: string) =>
    apiFetch<AdvisorResponse>(`${API_PREFIX}/advisor/ask`, {
      method: "POST",
      body: JSON.stringify({
        question,
        user_id: userId,
        user_skills: userSkills ?? null,
        resume_summary: resumeSummary ?? null,
      }),
    }),
  /**
   * Streaming advisor — SSE frames of raw text tokens, terminated by "[DONE]".
   * Reads the fetch body stream directly (EventSource can't send a POST body).
   */
  stream: async (
    question: string,
    userId: string,
    onToken: (token: string) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const res = await fetch(`${API_BASE}${API_PREFIX}/advisor/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, user_id: userId }),
      signal,
    });
    if (!res.ok || !res.body) {
      throw new ApiError("STREAM_ERROR", "Advisor stream failed to start", {}, res.status);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const chunk = line.slice(6);
        if (chunk === "[DONE]") return;
        if (chunk.startsWith("[ERROR]")) throw new ApiError("STREAM_ERROR", chunk, {}, 500);
        onToken(chunk);
      }
    }
  },
};

// ── Analytics ────────────────────────────────────────────────────────

export const analytics = {
  summary: () => apiFetch<DashboardSummary>(`${API_PREFIX}/analytics/summary`),
  topSkills: (params: { limit?: number; country?: string } = {}) =>
    apiFetch<TopSkill[]>(`${API_PREFIX}/analytics/skills/top${qs(params)}`),
  remoteBreakdown: (params: { country?: string } = {}) =>
    apiFetch<RemoteBreakdown[]>(`${API_PREFIX}/analytics/remote${qs(params)}`),
  topCompanies: (params: { limit?: number; country?: string } = {}) =>
    apiFetch<TopCompany[]>(`${API_PREFIX}/analytics/companies/top${qs(params)}`),
  topLocations: (params: { limit?: number } = {}) =>
    apiFetch<TopLocation[]>(`${API_PREFIX}/analytics/locations/top${qs(params)}`),
  salaryBySkill: (skill: string, country?: string) =>
    apiFetch<SalaryBySkill | null>(`${API_PREFIX}/analytics/salary${qs({ skill, country })}`),
  forecast: (skill: string) =>
    apiFetch<SkillForecast | null>(`${API_PREFIX}/analytics/forecast/${encodeURIComponent(skill)}`),
};

// ── Resumes ──────────────────────────────────────────────────────────

export const resumes = {
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<{ resume_id: string; filename: string; text_length: number }>(
      `${API_PREFIX}/resumes/upload`,
      { method: "POST", body: form, isForm: true, auth: true }
    );
  },
  list: () => apiFetch<ResumeSummary[]>(`${API_PREFIX}/resumes/`, { auth: true }),
  remove: (id: string) => apiFetch<{ deleted: string }>(`${API_PREFIX}/resumes/${id}`, { method: "DELETE", auth: true }),
};

// ── Applications ─────────────────────────────────────────────────────

export const applications = {
  save: (jobId: string, notes?: string) =>
    apiFetch<{ application_id: string; status: string }>(`${API_PREFIX}/applications/`, {
      method: "POST",
      auth: true,
      body: JSON.stringify({ job_id: jobId, notes: notes ?? null }),
    }),
  list: () => apiFetch<Application[]>(`${API_PREFIX}/applications/`, { auth: true }),
  updateStatus: (id: string, status: ApplicationStatus, notes?: string) =>
    apiFetch<{ id: string; status: string }>(`${API_PREFIX}/applications/${id}`, {
      method: "PATCH",
      auth: true,
      body: JSON.stringify({ status, notes: notes ?? null }),
    }),
  remove: (id: string) =>
    apiFetch<{ deleted: string }>(`${API_PREFIX}/applications/${id}`, { method: "DELETE", auth: true }),
};

// ── Health ───────────────────────────────────────────────────────────

export interface HealthNode {
  status: "ok" | "degraded" | "error";
  detail: string;
}
export interface HealthResponse {
  overall: string;
  environment: string;
  nodes: Record<string, HealthNode>;
}

export const health = {
  // /health is unwrapped JSON (no {data, error} envelope), unlike every other route.
  check: async (): Promise<HealthResponse> => {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new ApiError("HEALTH_ERROR", "Health check failed", {}, res.status);
    return res.json();
  },
};
