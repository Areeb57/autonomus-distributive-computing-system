/**
 * ADC API & WebSocket Client Service for frontenda.
 * Integrates with FastAPI backend running on port 8000.
 */

import type {
  Project,
  UserProfile,
  HardwareProfile,
  ContributionSettings,
} from '../types';


const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ||
  (typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    : 'ws://localhost:8000');

// Token management in localStorage
const TOKEN_KEY = 'adc_auth_token_v1';

export const getAuthToken = (): string | null => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setAuthToken = (token: string | null) => {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // ignore
  }
};

/**
 * Standard fetch wrapper with auth header, cookies, and JSON parsing.
 */
async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Double-Submit CSRF and session cookies
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // ── Authentication ──────────────────────────────────────────────────────────

  async getMe(): Promise<UserProfile> {
    return fetchApi<UserProfile>('/api/v1/auth/me');
  },

  async login(username: string, password: string): Promise<{ access_token: string; user: UserProfile }> {
    const res = await fetchApi<{ access_token: string; user: UserProfile }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },

  async register(data: {
    email: string;
    username: string;
    displayName: string;
    password: string;
  }): Promise<{ access_token: string; user: UserProfile }> {
    const res = await fetchApi<{ access_token: string; user: UserProfile }>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email: data.email,
        username: data.username,
        display_name: data.displayName,
        password: data.password,
      }),
    });
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },

  async logout(): Promise<void> {
    try {
      await fetchApi('/api/v1/auth/logout', { method: 'POST' });
    } finally {
      setAuthToken(null);
    }
  },

  // ── Projects ────────────────────────────────────────────────────────────────

  async getProjects(myProjects: boolean = false): Promise<Project[]> {
    const query = myProjects ? '?my_projects=true' : '';
    const res = await fetchApi<{ projects: Project[]; total: number }>(`/api/v1/projects${query}`);
    return res.projects;
  },

  async getProject(projectId: string): Promise<Project> {
    return fetchApi<Project>(`/api/v1/projects/${projectId}`);
  },

  async createProject(projectData: Partial<Project>): Promise<Project> {
    return fetchApi<Project>('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify({
        name: projectData.name,
        description: projectData.description || '',
        trainingObjective: projectData.trainingObjective || '',
        modelArchitecture: projectData.modelArchitecture || 'Diffusion (UNet / DiT 180M)',
        datasetName: projectData.datasetName || '',
        datasetDescription: projectData.datasetDescription || '',
        expectedDuration: projectData.expectedDuration || '3 hours',
        visibility: projectData.visibility || 'public',
        workersNeeded: projectData.workersNeeded || 4,
        trainingStrategy: projectData.trainingStrategy || 'data_parallel',
        trainingConfig: projectData.trainingConfig,
        requirements: projectData.requirements,
      }),
    });
  },

  async putProjectOnline(projectId: string): Promise<{ projectCode: string; status: string; project: Project }> {
    return fetchApi(`/api/v1/projects/${projectId}/online`, { method: 'POST' });
  },

  async pauseProject(projectId: string): Promise<{ status: string }> {
    return fetchApi(`/api/v1/projects/${projectId}/pause`, { method: 'POST' });
  },

  async resumeProject(projectId: string): Promise<{ status: string }> {
    return fetchApi(`/api/v1/projects/${projectId}/resume`, { method: 'POST' });
  },

  async stopProject(projectId: string): Promise<{ status: string }> {
    return fetchApi(`/api/v1/projects/${projectId}/stop`, { method: 'POST' });
  },

  async joinByCode(
    code: string,
    resources?: Partial<ContributionSettings>
  ): Promise<{ projectId: string; membership: any; message: string }> {
    return fetchApi('/api/v1/projects/join-by-code', {
      method: 'POST',
      body: JSON.stringify({
        code: code.trim(),
        cpuCores: resources?.cpuCores,
        ramGB: resources?.ramBudgetGB,
        gpuEnabled: resources?.gpuEnabled,
        storageGB: resources?.storageBudgetGB,
        networkPreference: resources?.networkPreference,
      }),
    });
  },

  // ── Hardware & Resources ────────────────────────────────────────────────────

  async getHardwareAndResources(): Promise<{
    hardwareProfile: HardwareProfile;
    contributionSettings: ContributionSettings;
  }> {
    return fetchApi('/api/v1/resources/me');
  },

  async updateResourceSettings(settings: Partial<ContributionSettings>): Promise<ContributionSettings> {
    return fetchApi('/api/v1/resources/me', {
      method: 'PATCH',
      body: JSON.stringify({
        cpuCores: settings.cpuCores,
        ramBudgetGB: settings.ramBudgetGB,
        gpuEnabled: settings.gpuEnabled,
        selectedGpu: settings.selectedGpu,
        storageBudgetGB: settings.storageBudgetGB,
        networkPreference: settings.networkPreference,
        globalPaused: settings.globalPaused,
      }),
    });
  },

  async pauseAllResources(): Promise<{ globalPaused: boolean }> {
    return fetchApi('/api/v1/resources/me/pause-all', { method: 'POST' });
  },

  async resumeAllResources(): Promise<{ globalPaused: boolean }> {
    return fetchApi('/api/v1/resources/me/resume-all', { method: 'POST' });
  },

  // ── Checkpoints ─────────────────────────────────────────────────────────────

  async getCheckpoints(projectId: string): Promise<any> {
    return fetchApi(`/api/v1/projects/${projectId}/checkpoints`);
  },

  // ── Real-Time WebSocket Connection ──────────────────────────────────────────

  connectWebSocket(
    projectId: string | null,
    onEvent: (event: { type: string; projectId?: string; data?: any }) => void,
    onStatusChange?: (isConnected: boolean) => void
  ): () => void {
    const wsUrl = `${WS_BASE}/api/v1/ws/events`;
    let ws: WebSocket | null = null;
    let shouldReconnect = true;
    let reconnectTimeout: any = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          onStatusChange?.(true);
          // If subscribed to a specific project, send subscription envelope
          if (projectId) {
            ws?.send(
              JSON.stringify({
                action: 'subscribe',
                project_id: projectId,
              })
            );
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            onEvent(data);
          } catch {
            // raw message
          }
        };

        ws.onclose = () => {
          onStatusChange?.(false);
          if (shouldReconnect) {
            reconnectTimeout = setTimeout(connect, 3000);
          }
        };

        ws.onerror = () => {
          onStatusChange?.(false);
        };
      } catch {
        onStatusChange?.(false);
        if (shouldReconnect) {
          reconnectTimeout = setTimeout(connect, 5000);
        }
      }
    };

    connect();

    // Return cleanup unsubscribe function
    return () => {
      shouldReconnect = false;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) {
        try {
          ws.close();
        } catch {
          // ignore
        }
      }
    };
  },
};
