
import type { AgentStatus } from './agent';

export type AgentProfile = Pick<
    AgentStatus,
    | 'agentId'
    | 'hostname'
    | 'version'
    | 'cpuModel'
    | 'cpuArchitecture'
    | 'physicalCpuCores'
    | 'logicalCpuCores'
    | 'totalRamGB'
    | 'gpuVendor'
    | 'gpuModel'
    | 'gpuComputeBackend'
    | 'totalGpuMemoryGB'
    | 'totalDiskGB'
    | 'osName'
    | 'osVersion'
    | 'workerCompatibilityStatus'
    | 'workerCompatibilityDetails'
>;

const PROFILE_KEY = 'adc_agent_profile';

export function saveAgentProfile(
    status: AgentStatus
): void {
    const {
        agentId,
        hostname,
        version,
        cpuModel,
        cpuArchitecture,
        physicalCpuCores,
        logicalCpuCores,
        totalRamGB,
        gpuVendor,
        gpuModel,
        gpuComputeBackend,
        totalGpuMemoryGB,
        totalDiskGB,
        osName,
        osVersion,
        workerCompatibilityStatus,
        workerCompatibilityDetails
    } = status;

    const profile: AgentProfile = {
        agentId,
        hostname,
        version,
        cpuModel,
        cpuArchitecture,
        physicalCpuCores,
        logicalCpuCores,
        totalRamGB,
        gpuVendor,
        gpuModel,
        gpuComputeBackend,
        totalGpuMemoryGB,
        totalDiskGB,
        osName,
        osVersion,
        workerCompatibilityStatus,
        workerCompatibilityDetails
    };

    sessionStorage.setItem(
        PROFILE_KEY,
        JSON.stringify(profile)
    );
}

export function loadAgentProfile(): AgentProfile | null {
    try {
        const saved = sessionStorage.getItem(PROFILE_KEY);

        return saved
            ? JSON.parse(saved) as AgentProfile
            : null;
    } catch {
        return null;
    }
}

export function clearAgentProfile(): void {
    sessionStorage.removeItem(PROFILE_KEY);
}
