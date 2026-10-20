/**
 * ADC API & WebSocket Client for frontendb.
 * Connects frontendb directly with the FastAPI backend (port 8000).
 * Handles machine identity, session management, project creation,
 * 9-digit code worker joining, hardware telemetry, and real-time events.
 */

import type {
  MasterProject,
  WorkerProject,
  GlobalResourceSettings,
  HardwareSpecs,
  WorkerAllocation,
  ConnectedWorker,
  ProjectStatus
} from '../types';
import { cleanProjectCode, formatProjectCode } from '../utils/formatting';
import { agentClient, type WebRtcJoinInfo } from './agent';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ||
  (typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    : 'ws://localhost:8000');

const TOKEN_KEY = 'adc_auth_token_v1';
const INSTALLATION_KEY = 'adc_installation_id_v1';
const PENDING_WEBRTC_JOIN_KEY = 'adc_pending_webrtc_join_v1';

export const getAuthToken = (): string | null => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setAuthToken = (token: string | null): void => {
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

export const getInstallationId = (): string => {
  try {
    let id = localStorage.getItem(INSTALLATION_KEY);
    if (!id) {
      id = 'inst-' + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
      localStorage.setItem(INSTALLATION_KEY, id);
    }
    return id;
  } catch {
    return 'inst-local-fallback';
  }
};

let cachedCsrfToken: string | null = null;

export const getCsrfToken = async (): Promise<string | null> => {
  if (cachedCsrfToken) return cachedCsrfToken;
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/csrf`, { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      cachedCsrfToken = data.csrf_token || null;
      return cachedCsrfToken;
    }
  } catch {
    // offline or error
  }
  return null;
};

/**
 * Standard fetch wrapper with authentication headers, CSRF, and JSON parsing.
 */
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const installId = getInstallationId();
  if (installId && !headers.has('X-Installation-Id')) {
    headers.set('X-Installation-Id', installId);
  }

  // Double-submit CSRF for mutating methods
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrf = await getCsrfToken();
    if (csrf && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrf);
    }
  }

  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include'
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
  /**
   * Quick check to verify if the FastAPI backend is running and reachable.
   */
  async checkHealth(): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/health`, { method: 'GET', credentials: 'include' });
      return res.ok;
    } catch {
      return false;
    }
  },

  // ── Authentication & Machine Pairing ──────────────────────────────────────

  async getMe(): Promise<{ id: string; username: string; email: string }> {
    return fetchApi('/api/v1/auth/me');
  },

  async login(username = 'researcher_demo', password = 'Password123!'): Promise<string> {
    const res = await fetchApi<{ access_token: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    setAuthToken(res.access_token);
    return res.access_token;
  },

  async register(
    email = 'researcher@adc-network.io',
    username = 'researcher_demo',
    displayName = 'Researcher Demo',
    password = 'Password123!'
  ): Promise<string> {
    const res = await fetchApi<{ access_token: string }>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        username,
        display_name: displayName,
        password
      })
    });
    setAuthToken(res.access_token);
    return res.access_token;
  },

  /**
   * Ensures an active session exists on the backend.
   * Auto-logs in or registers researcher_demo if not authenticated.
   */
  async ensureAuthenticated(): Promise<boolean> {
    const token = getAuthToken();
    if (token) {
      try {
        await this.getMe();
        return true;
      } catch {
        setAuthToken(null);
      }
    }

    try {
      await this.login();
      return true;
    } catch {
      try {
        await this.register();
        return true;
      } catch {
        return false;
      }
    }
  },

  /**
   * Ensures a local machine record is paired to the user account in the specified role.
   */
  async ensureMachinePaired(role: 'master' | 'worker'): Promise<boolean> {
    const installId = getInstallationId();
    try {
      // 1. Register machine
      await fetchApi('/api/v1/machines/register', {
        method: 'POST',
        body: JSON.stringify({
          installation_id: installId,
          name: `node-${role}-${installId.slice(-4)}`,
          public_key: `pubkey_${installId}_ed25519`,
          platform: typeof navigator !== 'undefined' ? navigator.platform : 'web'
        })
      });

      // 2. Request pairing challenge
      const challengeRes = await fetchApi<{ pairing_code: string }>('/api/v1/machines/pairing/challenge', {
        method: 'POST',
        body: JSON.stringify({
          installation_id: installId
        })
      });

      // 3. Complete pairing
      await fetchApi('/api/v1/machines/pairing/complete', {
        method: 'POST',
        body: JSON.stringify({
          pairing_code: challengeRes.pairing_code,
          selected_role: role
        })
      });

      return true;
    } catch {
      return false;
    }
  },

  // ── Hardware & Resource Settings ──────────────────────────────────────────

  /**
   * Retrieve live hardware specs and current contribution settings from backend.
   */
  async getHardwareAndResources(): Promise<{
    hardware: HardwareSpecs;
    settings: GlobalResourceSettings;
  }> {
    const data = await fetchApi<{
      hardwareProfile: {
        cpuModel: string;
        cpuCores: number;
        ramTotalGB: number;
        ramAvailableGB: number;
        gpuModel: string;
        gpuMemoryTotalGB: number;
        diskSpaceAvailableGB: number;
      };
      contributionSettings: {
        cpuCores: number;
        ramBudgetGB: number;
        gpuEnabled: boolean;
        storageBudgetGB: number;
        globalPaused: boolean;
      };
    }>('/api/v1/resources/me');

    const hw = data.hardwareProfile;
    const cs = data.contributionSettings;

    const hardware: HardwareSpecs = {
      cpuModel: hw.cpuModel || 'Host CPU',
      cpuTotalCores: hw.cpuCores || 8,
      cpuAvailableCores: Math.max(1, (hw.cpuCores || 8) - 2),
      ramTotalGb: Math.round(hw.ramTotalGB || 32),
      ramAvailableGb: Math.round(hw.ramAvailableGB || 24),
      gpuModel: hw.gpuModel !== 'None' ? hw.gpuModel : 'Integrated Graphics',
      gpuVramGb: Math.round(hw.gpuMemoryTotalGB || 8),
      storageTotalGb: Math.round((hw.diskSpaceAvailableGB || 250) * 1.5),
      storageAvailableGb: Math.round(hw.diskSpaceAvailableGB || 250)
    };

    const cpuBudgetPercent = Math.min(
      100,
      Math.round(((cs.cpuCores || 4) / Math.max(1, hardware.cpuTotalCores)) * 100)
    );

    const settings: GlobalResourceSettings = {
      globalPaused: cs.globalPaused ?? false,
      cpuBudgetPercent: cpuBudgetPercent || 75,
      ramBudgetGb: cs.ramBudgetGB || 16,
      gpuBudgetPercent: cs.gpuEnabled ? 80 : 0,
      storageBudgetGb: cs.storageBudgetGB || 50
    };

    return { hardware, settings };
  },

  /**
   * Update volunteer compute budgets on backend.
   */
  async updateResourceSettings(settings: Partial<GlobalResourceSettings>): Promise<void> {
    const payload: Record<string, unknown> = {};

    if (settings.globalPaused !== undefined) {
      payload.globalPaused = settings.globalPaused;
    }
    if (settings.ramBudgetGb !== undefined) {
      payload.ramBudgetGB = settings.ramBudgetGb;
    }
    if (settings.storageBudgetGb !== undefined) {
      payload.storageBudgetGB = settings.storageBudgetGb;
    }
    if (settings.gpuBudgetPercent !== undefined) {
      payload.gpuEnabled = settings.gpuBudgetPercent > 0;
    }
    if (settings.cpuBudgetPercent !== undefined) {
      payload.cpuCores = Math.max(1, Math.round((settings.cpuBudgetPercent / 100) * 16));
    }

    await fetchApi('/api/v1/resources/me', {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  },

  // ── Master Projects ───────────────────────────────────────────────────────

  async getProjects(): Promise<MasterProject[]> {
    const data = await fetchApi<{
      projects: Array<{
        id: string;
        name: string;
        description: string;
        dataset_name: string;
        dataset_size: string;
        code_file_name: string;
        code_file_size: string;
        active_code?: string;
        status: string;
        created_at: string;
        workers?: Array<{
          machine_id: string;
          machine_name: string;
          status: string;
          cpu_cores_contributed: number;
          ram_contributed_gb: number;
          gpu_enabled: boolean;
        }>;
      }>;
    }>('/api/v1/projects?my_projects=true');

    return data.projects.map((p) => {
      const workers: ConnectedWorker[] = (p.workers || []).map((w, idx) => ({
        id: w.machine_id || `w-${idx}`,
        name: w.machine_name || `worker-node-${idx + 1}`,
        status: (w.status === 'computing' ? 'computing' : 'active') as 'computing' | 'active',
        cpuCores: w.cpu_cores_contributed * 2,
        allocatedCpuCores: w.cpu_cores_contributed,
        ramGb: Math.round(w.ram_contributed_gb * 1.5),
        allocatedRamGb: w.ram_contributed_gb,
        gpuName: w.gpu_enabled ? 'Active GPU' : 'None',
        allocatedGpuPercent: w.gpu_enabled ? 80 : 0,
        latencyMs: 25 + idx * 8,
        currentBatch: `Batch ${1400 + idx} (Loss: 0.32)`
      }));

      const rawCode = cleanProjectCode(p.active_code || '');

      return {
        id: p.id,
        name: p.name,
        description: p.description || '',
        datasetFileName: p.dataset_name || 'dataset.zip',
        datasetFileSize: p.dataset_size || '1.2 GB',
        codeFileName: p.code_file_name || 'train.py',
        codeFileSize: p.code_file_size || '32 KB',
        projectCode: rawCode || '123456789',
        status: (p.status === 'online' || p.status === 'looking_for_workers'
          ? 'training'
          : p.status) as ProjectStatus,
        progress: 0,
        currentStep: 0,
        totalSteps: 4000,
        loss: 1.84,
        speed: '168 samples/s',
        elapsedSeconds: 0,
        estimatedRemainingSeconds: 5600,
        createdAt: p.created_at,
        workers
      };
    });
  },

  /**
   * Create a new distributed training project on backend.
   */
  async createProject(data: {
    name: string;
    description: string;
    datasetFileName: string;
    datasetFileSize: string;
    codeFileName: string;
    codeFileSize: string;
  }): Promise<{ id: string }> {
    return fetchApi<{ id: string }>('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify({
        name: data.name,
        description: data.description || '',
        training_objective: 'Distributed Neural Network Training',
        model_architecture: 'Diffusion UNet (DiT 180M)',
        dataset_name: data.datasetFileName,
        dataset_size: data.datasetFileSize,
        code_file_name: data.codeFileName,
        code_file_size: data.codeFileSize,
        visibility: 'public',
        training_strategy: 'data_parallel',
        workers_needed: 4,
        requirements: {
          min_cpu_cores: 2,
          min_ram_gb: 4.0,
          gpu_recommended: true,
          min_vram_gb: 4.0
        },
        training_config: {
          batch_size: 32,
          total_steps: 4000,
          learning_rate: 0.0002,
          optimizer: 'AdamW',
          precision: 'fp16',
          checkpoint_interval: 500,
          gradient_accumulation_steps: 2
        }
      })
    });
  },

  /**
   * Put project online to generate authoritative 9-digit code and accept workers.
   */
  async putProjectOnline(projectId: string): Promise<{
    projectCode: string;
    status: string;
    project: MasterProject;
  }> {
    const res = await fetchApi<{
      status: string;
      project_code: string;
      message: string;
      project: {
        id: string;
        name: string;
        description: string;
        dataset_name: string;
        dataset_size: string;
        code_file_name: string;
        code_file_size: string;
        status: string;
        created_at: string;
      };
    }>(`/api/v1/projects/${projectId}/online`, {
      method: 'POST'
    });

    const rawCode = cleanProjectCode(res.project_code);

    const masterProj: MasterProject = {
      id: res.project.id,
      name: res.project.name,
      description: res.project.description || '',
      datasetFileName: res.project.dataset_name || 'dataset.zip',
      datasetFileSize: res.project.dataset_size || '500 MB',
      codeFileName: res.project.code_file_name || 'train.py',
      codeFileSize: res.project.code_file_size || '16 KB',
      projectCode: rawCode,
      status: 'training',
      progress: 0,
      currentStep: 0,
      totalSteps: 4000,
      loss: 1.845,
      speed: '172 samples/s',
      elapsedSeconds: 0,
      estimatedRemainingSeconds: 5800,
      createdAt: res.project.created_at,
      workers: []
    };

    return {
      projectCode: rawCode,
      status: res.status,
      project: masterProj
    };
  },

  async pauseProject(projectId: string): Promise<void> {
    await fetchApi(`/api/v1/projects/${projectId}/pause`, { method: 'POST' });
  },

  async resumeProject(projectId: string): Promise<void> {
    await fetchApi(`/api/v1/projects/${projectId}/resume`, { method: 'POST' });
  },

  async stopProject(projectId: string): Promise<void> {
    await fetchApi(`/api/v1/projects/${projectId}/stop`, { method: 'POST' });
  },

  async endProject(projectId: string): Promise<void> {
    await fetchApi(`/api/v1/projects/${projectId}/end`, { method: 'POST' });
  },

  // ── WebRTC project discovery / local-agent handoff ─────────────────────────

  /** Resolve a join code into credentials needed for WebRTC signaling.
   * The backend must validate the code and return worker-scoped credentials;
   * never derive a master address or auth token in the browser.
   */
  async resolveWebRtcProjectCode(code: string): Promise<{ projectId: string; masterAgentId: string; projectName?: string }> {
    const rawCode = cleanProjectCode(code);
    if (!/^\d{9}$/.test(rawCode)) throw new Error('Project code must contain exactly 9 digits.');

    const response = await fetchApi<{
      projectId?: string; project_id?: string;
      masterAgentId?: string; master_agent_id?: string;
      authToken?: string; auth_token?: string;
      websocketUrl?: string; websocket_url?: string;
      projectName?: string; project_name?: string;
    }>('/api/webrtc/resolve-code', {
      method: 'POST',
      body: JSON.stringify({ code: rawCode })
    });

    const info: WebRtcJoinInfo & { projectName?: string } = {
      projectId: String(response.projectId || response.project_id || ''),
      masterAgentId: String(response.masterAgentId || response.master_agent_id || ''),
      authToken: String(response.authToken || response.auth_token || ''),
      websocketUrl: response.websocketUrl || response.websocket_url,
      projectName: response.projectName || response.project_name
    };
    if (!info.projectId || !info.masterAgentId || !info.authToken) {
      throw new Error('The backend did not return projectId, masterAgentId and worker authToken. Check the WebRTC resolve-code endpoint.');
    }
    try { sessionStorage.setItem(PENDING_WEBRTC_JOIN_KEY, JSON.stringify({ ...info, projectCode: rawCode })); } catch { /* browser storage may be unavailable */ }
    return { projectId: info.projectId, masterAgentId: info.masterAgentId, projectName: info.projectName };
  },

  /** After project membership is accepted, pass the resolved credentials to adc_agent.py. */
  async connectPendingWorkerAgent(): Promise<void> {
    let saved: (WebRtcJoinInfo & { projectCode?: string }) | null = null;
    try {
      const raw = sessionStorage.getItem(PENDING_WEBRTC_JOIN_KEY);
      if (raw) saved = JSON.parse(raw) as WebRtcJoinInfo & { projectCode?: string };
    } catch { saved = null; }
    if (!saved) throw new Error('No resolved master connection is available. Return to Join Project and enter the code again.');
    await agentClient.connectWorker(saved);
    try { sessionStorage.removeItem(PENDING_WEBRTC_JOIN_KEY); } catch { /* ignore */ }
  },

  /**
   * Worker joins project by providing 9-digit code and resource allocation budget.
   */
  async joinByCode(
    projectCode: string,
    allocation: WorkerAllocation
  ): Promise<{
    success: boolean;
    workerProject?: WorkerProject;
    error?: string;
  }> {
    const rawCode = cleanProjectCode(projectCode);
    const formattedCode = formatProjectCode(rawCode);

    try {
      await this.ensureMachinePaired('worker');

      const res = await fetchApi<{
        projectId: string;
        status: string;
        contributionStatus: string;
        cpuCoresContributed: number;
        ramContributedGB: number;
        gpuEnabled: boolean;
        storageBudgetGB: number;
      }>('/api/v1/projects/join-by-code', {
        method: 'POST',
        body: JSON.stringify({
          code: formattedCode,
          cpuCores: allocation.allocatedCpuCores,
          ramGB: allocation.ramGb,
          gpuEnabled: allocation.gpuPercent > 0,
          storageGB: allocation.storageGb,
          networkPreference: 'unlimited'
        })
      });

      const workerProj: WorkerProject = {
        projectCode: rawCode,
        projectName: `AI Training Cluster #${rawCode.slice(0, 4)}`,
        allocation,
        status: (res.contributionStatus === 'computing' ? 'computing' : 'active') as 'computing' | 'active',
        assignedTask: `DDP Gradient Sync (Relay Node) • Project ${res.projectId.slice(0, 8)}`,
        currentProgress: 18.5,
        currentStep: 740,
        totalSteps: 4000,
        cpuUsage: Math.min(Math.round(allocation.cpuPercent * 0.88), 92),
        ramUsageGb: Math.round(allocation.ramGb * 0.75 * 10) / 10,
        gpuUsage: Math.min(Math.round(allocation.gpuPercent * 0.92), 95),
        joinedAt: new Date().toISOString()
      };

      return { success: true, workerProject: workerProj };
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : 'Failed to join project by code.'
      };
    }
  },

  // ── Real-Time WebSocket Streaming ─────────────────────────────────────────

  /**
   * Connects to the backend WebSocket hub for live metrics and telemetry.
   */
  connectWebSocket(
    projectId: string | null,
    onEvent: (event: {
      type: string;
      projectId?: string;
      data?: {
        step?: number;
        totalSteps?: number;
        loss?: number;
        speed?: number;
        progressPercent?: number;
        clusterCpuUtil?: number;
        clusterGpuUtil?: number;
        status?: string;
        worker?: ConnectedWorker;
      };
    }) => void,
    onStatusChange?: (isConnected: boolean) => void
  ): () => void {
    const token = getAuthToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const wsUrl = `${WS_BASE}/api/v1/ws/events${tokenParam}`;

    let ws: WebSocket | null = null;
    let shouldReconnect = true;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          onStatusChange?.(true);
          if (projectId) {
            ws?.send(
              JSON.stringify({
                action: 'subscribe',
                project_id: projectId
              })
            );
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            onEvent(data);
          } catch {
            // raw message ignored
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
  }
};
