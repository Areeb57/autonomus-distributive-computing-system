/**
 * Client for the local ADC Python agent (adc_agent.py).
 * The agent decides the role (master / worker / none); the dashboard follows it.
 */

import type { Role } from '../types';

const AGENT_URL = import.meta.env.VITE_AGENT_URL || 'http://127.0.0.1:8765';


export interface AgentStatus {
  // Identity
  agentId: string;
  userId: string | null;
  machineId: string | null;
  workerId: string | null;
  projectId: string | null;

  // Agent and operating system
  role: Role;
  hostname: string;
  version: string;
  osName: string;
  osVersion: string;
  workerCompatibilityStatus: string;
  workerCompatibilityDetails: string[];
  uptimeSeconds: number;

  // CPU
  cpuModel: string;
  cpuArchitecture: string;
  physicalCpuCores: number | null;
  logicalCpuCores: number;
  cpuUtilizationPercent: number | null;
  availableCpuCapacityPercent: number | null;

  // RAM
  totalRamGB: number | null;
  availableRamGB: number | null;

  // GPU
  gpuVendor: string;
  gpuModel: string;
  gpuComputeBackend: string;
  totalGpuMemoryGB: number | null;
  availableGpuMemoryGB: number | null;

  // Disk
  totalDiskGB: number | null;
  availableDiskGB: number | null;

  // Network
  networkUploadMbps: number | null;
  networkDownloadMbps: number | null;
  networkLatencyMs: number | null;
  packetLossPercent: number | null;
  connectionStability: string;
  connectionUptimeSeconds: number;
}


export interface WebRtcJoinInfo {
  masterAgentId: string;
  projectId: string;
  authToken: string;
  websocketUrl?: string;
}

async function postToLocalAgent(path: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(`${AGENT_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(payload)
  });
  let body: Record<string, unknown> = {};
  try { body = await response.json() as Record<string, unknown>; } catch { /* empty response */ }
  if (!response.ok) {
    throw new Error(String(body.error || body.detail || `Local ADC agent returned HTTP ${response.status}`));
  }
  return body;
}


export const agentClient = {
  /** Tell the local Python agent to enter a role for the selected project. */
  async setRole(role: Role, projectId?: string): Promise<Record<string, unknown>> {
    return postToLocalAgent('/agent/role', { role, ...(projectId ? { projectId } : {}) });
  },

  /** Pass website-resolved WebRTC credentials to the local worker agent. */
  async connectWorker(info: WebRtcJoinInfo): Promise<Record<string, unknown>> {
    return postToLocalAgent('/agent/connect', {
      masterAgentId: info.masterAgentId,
      projectId: info.projectId,
      authToken: info.authToken,
      ...(info.websocketUrl ? { websocketUrl: info.websocketUrl } : {})
    });
  },

  /**
   * Returns the agent's status, or null when the agent is not running / unreachable.
   */
  async getStatus(): Promise<AgentStatus | null> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    try {
      const res = await fetch(`${AGENT_URL}/agent/status`, {
        cache: 'no-store',
        signal: controller.signal
      });
      if (!res.ok) return null;
      const data = await res.json();
      const role: Role = data.role === 'master' || data.role === 'worker' ? data.role : 'none';

      return {
        agentId: String(data.agentId ?? ''),
        userId: data.userId ?? null,
        machineId: data.machineId ?? null,
        workerId: data.workerId ?? null,
        projectId: data.projectId ?? null,

        role,
        hostname: String(data.hostname ?? ''),
        version: String(data.version ?? ''),
        osName: String(data.osName ?? 'Unknown'),
        osVersion: String(data.osVersion ?? 'Unknown'),
        workerCompatibilityStatus:
          String(data.workerCompatibilityStatus ?? 'unknown'),
        workerCompatibilityDetails:
          Array.isArray(data.workerCompatibilityDetails)
            ? data.workerCompatibilityDetails.map(String)
            : [],
        uptimeSeconds: Number(data.uptimeSeconds ?? 0),

        cpuModel: String(data.cpuModel ?? 'Unknown'),
        cpuArchitecture: String(data.cpuArchitecture ?? 'Unknown'),
        physicalCpuCores: data.physicalCpuCores ?? null,
        logicalCpuCores: Number(data.logicalCpuCores ?? 0),
        cpuUtilizationPercent: data.cpuUtilizationPercent ?? null,
        availableCpuCapacityPercent:
          data.availableCpuCapacityPercent ?? null,

        totalRamGB: data.totalRamGB ?? null,
        availableRamGB: data.availableRamGB ?? null,

        gpuVendor: String(data.gpuVendor ?? 'Unknown'),
        gpuModel: String(data.gpuModel ?? 'Not detected'),
        gpuComputeBackend: String(data.gpuComputeBackend ?? 'Unknown'),
        totalGpuMemoryGB: data.totalGpuMemoryGB ?? null,
        availableGpuMemoryGB: data.availableGpuMemoryGB ?? null,

        totalDiskGB: data.totalDiskGB ?? null,
        availableDiskGB: data.availableDiskGB ?? null,

        networkUploadMbps: data.networkUploadMbps ?? null,
        networkDownloadMbps: data.networkDownloadMbps ?? null,
        networkLatencyMs: data.networkLatencyMs ?? null,
        packetLossPercent: data.packetLossPercent ?? null,
        connectionStability:
          String(data.connectionStability ?? 'unknown'),
        connectionUptimeSeconds:
          Number(data.connectionUptimeSeconds ?? 0)
      };

    } catch {
      return null;
    } finally {
      clearTimeout(timer);
    }
  }
};
