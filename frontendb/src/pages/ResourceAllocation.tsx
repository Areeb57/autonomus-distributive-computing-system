import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { ResourceSlider } from '../components/ResourceSlider';
import { ArrowLeft, CheckCircle2, Cpu, HardDrive, MemoryStick, Monitor, Network, RefreshCw, ShieldCheck } from 'lucide-react';
import { formatProjectCode } from '../utils/formatting';
import { agentClient } from '../services/agent';

/**
 * Hardware fields returned by the updated adc_agent.py.
 * Optional fields deliberately allow older agents / unavailable telemetry.
 */
interface AgentHardwareStatus {
  agentId?: string;
  role?: 'none' | 'master' | 'worker';
  hostname?: string;
  version?: string;
  cpuModel?: string;
  cpuArchitecture?: string;
  physicalCpuCores?: number | null;
  logicalCpuCores?: number | null;
  cpuUtilizationPercent?: number | null;
  availableCpuCapacityPercent?: number | null;
  totalRamGB?: number | null;
  availableRamGB?: number | null;
  gpuVendor?: string;
  gpuModel?: string;
  gpuComputeBackend?: string;
  totalGpuMemoryGB?: number | null;
  availableGpuMemoryGB?: number | null;
  totalDiskGB?: number | null;
  availableDiskGB?: number | null;
  networkUploadMbps?: number | null;
  networkDownloadMbps?: number | null;
  networkLatencyMs?: number | null;
  packetLossPercent?: number | null;
  connectionStability?: string;
  connectionUptimeSeconds?: number | null;
  osName?: string;
  osVersion?: string;
  workerCompatibilityStatus?: string;
  workerCompatibilityDetails?: string[];
  uptimeSeconds?: number | null;
}

const PROFILE_KEY = 'adc_agent_profile';

const PERMANENT_FIELDS: (keyof AgentHardwareStatus)[] = [
  'agentId', 'hostname', 'version', 'cpuModel', 'cpuArchitecture',
  'physicalCpuCores', 'logicalCpuCores', 'totalRamGB', 'gpuVendor',
  'gpuModel', 'gpuComputeBackend', 'totalGpuMemoryGB', 'totalDiskGB',
  'osName', 'osVersion', 'networkLatencyMs', 'packetLossPercent',
  'connectionStability', 'connectionUptimeSeconds',
  'workerCompatibilityStatus', 'workerCompatibilityDetails'
];

function readSavedProfile(): Partial<AgentHardwareStatus> {
  try {
    const raw = sessionStorage.getItem(PROFILE_KEY);
    return raw ? JSON.parse(raw) as Partial<AgentHardwareStatus> : {};
  } catch {
    return {};
  }
}

function savePermanentProfile(status: AgentHardwareStatus): void {
  try {
    const previous = readSavedProfile();
    const next: Partial<AgentHardwareStatus> = { ...previous };
    for (const field of PERMANENT_FIELDS) {
      const value = status[field];
      if (value !== undefined && value !== null) {
        (next as Record<string, unknown>)[field] = value;
      }
    }
    sessionStorage.setItem(PROFILE_KEY, JSON.stringify(next));
  } catch {
    // Storage can be unavailable in private/restricted browser contexts.
  }
}

const numberOrNull = (value: number | null | undefined): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? Math.max(0, value) : null;

const fmt = (value: number | null | undefined, digits = 1): string =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'Unavailable';

export const ResourceAllocation: React.FC = () => {
  const navigate = useNavigate();
  const { pendingWorkerCode, joinWorkerProject, workerProject } = useApp();

  const [profile, setProfile] = useState<Partial<AgentHardwareStatus>>(() => readSavedProfile());
  const [live, setLive] = useState<AgentHardwareStatus | null>(null);
  const [agentChecked, setAgentChecked] = useState(false);
  const [cpuPercent, setCpuPercent] = useState(50);
  const [ramGb, setRamGb] = useState(1);
  const [gpuPercent, setGpuPercent] = useState(50);
  const [storageGb, setStorageGb] = useState(1);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [isJoining, setIsJoining] = useState(false);

  // Keep the permanent profile in sessionStorage, while keeping live telemetry in React state only.
  const pollAgent = useCallback(async () => {
    const raw = await agentClient.getStatus();
    const status = raw as unknown as AgentHardwareStatus | null;
    setAgentChecked(true);
    if (!status) {
      setLive(null);
      return;
    }

    setLive(status);
    savePermanentProfile(status);
    setProfile(readSavedProfile());
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      await pollAgent();
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [pollAgent]);

  useEffect(() => {
    if (!pendingWorkerCode && !workerProject) {
      navigate('/worker/join');
    }
  }, [pendingWorkerCode, workerProject, navigate]);

  // Prefer the live agent response, then the saved static profile. Never use demo hardware
  // values as if they were measurements from the user's machine.
  const cpuModel = live?.cpuModel ?? profile.cpuModel ?? 'Not detected';
  const cpuArchitecture = live?.cpuArchitecture ?? profile.cpuArchitecture ?? 'Unknown';
  const physicalCores = live?.physicalCpuCores ?? profile.physicalCpuCores ?? null;
  const logicalCores = live?.logicalCpuCores ?? profile.logicalCpuCores ?? null;
  const totalRam = live?.totalRamGB ?? profile.totalRamGB ?? null;
  // Once the agent is live, treat its response as authoritative (including null values).
  // This prevents a saved GPU profile from another session/computer overriding a no-GPU result.
  const gpuVendor = live ? (live.gpuVendor || 'Unknown') : (profile.gpuVendor ?? 'Unknown');
  const gpuModel = live ? (live.gpuModel || 'Not detected') : (profile.gpuModel ?? 'Not detected');
  const gpuBackend = live ? (live.gpuComputeBackend || 'Unknown') : (profile.gpuComputeBackend ?? 'Unknown');
  const totalVram = live
    ? numberOrNull(live.totalGpuMemoryGB)
    : numberOrNull(profile.totalGpuMemoryGB);
  const totalDisk = live?.totalDiskGB ?? profile.totalDiskGB ?? null;
  const osName = live?.osName ?? profile.osName ?? 'Unknown';
  const osVersion = live?.osVersion ?? profile.osVersion ?? 'Unknown';
  const compatibility = live?.workerCompatibilityStatus ?? profile.workerCompatibilityStatus ?? 'unknown';
  const compatibilityDetails = live?.workerCompatibilityDetails ?? profile.workerCompatibilityDetails ?? [];

  const availableCpuPercent = numberOrNull(live?.availableCpuCapacityPercent);
  const cpuUtilization = numberOrNull(live?.cpuUtilizationPercent);
  const availableRam = numberOrNull(live?.availableRamGB);
  const availableVram = numberOrNull(live?.availableGpuMemoryGB);
  const availableDisk = numberOrNull(live?.availableDiskGB);
  const uploadMbps = numberOrNull(live?.networkUploadMbps);
  const downloadMbps = numberOrNull(live?.networkDownloadMbps);
  const latency = numberOrNull(live?.networkLatencyMs ?? profile.networkLatencyMs);
  const packetLoss = numberOrNull(live?.packetLossPercent ?? profile.packetLossPercent);

  const isUnavailableGpuLabel = (value: string | null | undefined): boolean => {
    const normalized = (value ?? '').trim().toLowerCase();
    return !normalized ||
      ['unknown', 'not detected', 'none', 'no gpu', 'no gpu detected', 'unavailable', 'n/a'].includes(normalized) ||
      normalized.includes('no supported gpu');
  };
  const gpuDetected = !isUnavailableGpuLabel(gpuModel) ||
    !isUnavailableGpuLabel(gpuVendor) ||
    !isUnavailableGpuLabel(gpuBackend) ||
    (totalVram !== null && totalVram > 0);
  const hasGpu = gpuDetected && totalVram !== null && totalVram > 0 && availableVram !== null && availableVram > 0;
  const gpuStatusMessage = !gpuDetected
    ? 'No GPU detected. You can still join using CPU, RAM and storage; GPU contribution will be set to 0%.'
    : !hasGpu
      ? 'GPU detected, but usable VRAM is unavailable. You can still join using CPU, RAM and storage without GPU acceleration.'
      : `GPU ready · ${fmt(availableVram)} GB VRAM available.`;
  const hasLiveCapacity = !!live && availableRam !== null && availableDisk !== null;
  const maxRam = availableRam ?? 0;
  const maxDisk = availableDisk ?? 0;
  // Keep one decimal place and round DOWN so the UI never permits more than the
  // agent's currently reported available capacity (for example, 0.6 GB stays 0.6).
  const maxRamSlider = Math.max(0, Math.floor((maxRam + 1e-8) * 10) / 10);
  const maxDiskSlider = Math.max(0, Math.floor((maxDisk + 1e-8) * 10) / 10);
  // Allow a 0.3 GB RAM minimum when the machine has at least that much free RAM.
  const minRamSlider = maxRamSlider >= 0.3 ? 0.3 : 0;
  const allocatedCores = logicalCores && logicalCores > 0
    ? Math.max(1, Math.round(logicalCores * cpuPercent / 100))
    : 0;
  const allocatedVram = hasGpu ? (availableVram! * gpuPercent / 100) : 0;

  // Clamp chosen allocations if available resources shrink while this page is open.
  useEffect(() => {
    // Do not clamp the defaults to zero before the agent's first live response.
    if (!live) return;
    setRamGb(current => Math.max(minRamSlider, Math.min(current, maxRamSlider)));
    setStorageGb(current => Math.min(current, maxDiskSlider));
  }, [live, minRamSlider, maxRamSlider, maxDiskSlider]);

  // The GPU control is disabled when GPU/VRAM is absent, so set its allocation to
  // zero automatically. This lets CPU-only machines continue without a GPU error.
  useEffect(() => {
    if (live && !hasGpu) {
      setGpuPercent(current => current === 0 ? current : 0);
    }
  }, [live, hasGpu]);

  const connectionLabel = useMemo(() => {
    if (!live) return agentChecked ? 'Agent disconnected' : 'Checking agent…';
    return `Connected · ${live.hostname || 'This machine'}`;
  }, [live, agentChecked]);

  const handleJoin = async () => {
    setJoinError(null);
    if (!live) {
      setJoinError('The ADC agent is not connected. Start adc_agent.py and wait for live resource information before joining.');
      return;
    }
    if (availableRam === null || availableDisk === null) {
      setJoinError('The agent did not report available RAM or disk space. Resource allocation is disabled until these measurements are available.');
      return;
    }
    if (ramGb <= 0 || ramGb > availableRam) {
      setJoinError(`RAM allocation must be greater than 0 and no more than ${fmt(availableRam)} GB currently available.`);
      return;
    }
    if (storageGb <= 0 || storageGb > availableDisk) {
      setJoinError(`Storage allocation must be greater than 0 and no more than ${fmt(availableDisk)} GB currently available.`);
      return;
    }
    const codeToJoin = pendingWorkerCode || workerProject?.projectCode || '';
    if (!codeToJoin) {
      setJoinError('No project code specified.');
      return;
    }

    setIsJoining(true);
    try {
      const result = await joinWorkerProject(codeToJoin, {
        cpuPercent,
        allocatedCpuCores: allocatedCores,
        ramGb,
        gpuPercent: hasGpu ? gpuPercent : 0,
        allocatedVramGb: hasGpu ? allocatedVram : 0,
        storageGb
      });
      if (result.success) navigate('/worker/progress');
      else setJoinError(result.error || 'Failed to join project.');
    } catch {
      setJoinError('Could not join the project. Please try again.');
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <div className="page-container">
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600 }}>Allocate Compute Resources</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
          Joining Project: <strong>{formatProjectCode(pendingWorkerCode || workerProject?.projectCode || '')}</strong>
        </p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: live ? 'var(--text-success, #16803d)' : 'var(--text-secondary)' }}>
            {connectionLabel}
          </span>
          <button type="button" className="btn btn-secondary" onClick={() => void pollAgent()} style={{ padding: '5px 9px', fontSize: 12 }}>
            <RefreshCw size={13} /> Refresh measurements
          </button>
          {profile.agentId && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Agent ID: {profile.agentId}</span>}
        </div>
      </div>

      {!live && (
        <div style={{ padding: '12px 14px', border: '1px solid var(--border-color, #ddd)', borderRadius: 'var(--radius-md)', marginBottom: 16, fontSize: 13 }}>
          {agentChecked
            ? 'Live measurements are unavailable. Saved hardware details are shown where possible, but joining is disabled until the agent reconnects.'
            : 'Connecting to adc_agent.py and reading hardware information…'}
        </div>
      )}

      <div className="hardware-summary">
        <div className="hardware-item">
          <span className="hardware-label"><Cpu size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} />Host CPU</span>
          <span className="hardware-val">{logicalCores ?? '—'} logical / {physicalCores ?? '—'} physical cores</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{cpuModel} · {cpuArchitecture}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Utilization: {fmt(cpuUtilization)}% · Capacity available: {fmt(availableCpuPercent)}%</span>
        </div>
        <div className="hardware-item">
          <span className="hardware-label"><MemoryStick size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} />System RAM</span>
          <span className="hardware-val">{fmt(availableRam)} GB available</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Total: {fmt(totalRam)} GB</span>
        </div>
        <div className="hardware-item">
          <span className="hardware-label"><Monitor size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} />Detected GPU</span>
          <span className="hardware-val">{gpuDetected ? gpuModel : 'No GPU detected'}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{gpuDetected ? `${gpuVendor} · Backend: ${gpuBackend}` : 'This worker can contribute CPU, RAM and storage without a GPU.'}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{hasGpu ? `VRAM: ${fmt(availableVram)} GB available / ${fmt(totalVram)} GB total` : 'GPU contribution: 0% (not required to join)'}</span>
        </div>
        <div className="hardware-item">
          <span className="hardware-label"><HardDrive size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} />Scratch Storage</span>
          <span className="hardware-val">{fmt(availableDisk)} GB available</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Total: {fmt(totalDisk)} GB</span>
        </div>
      </div>

      {live && !hasGpu && (
        <div role="status" style={{ padding: '11px 14px', border: '1px solid var(--border-color, #ddd)', borderRadius: 'var(--radius-md)', margin: '14px 0', fontSize: 13 }}>
          <strong>{gpuDetected ? 'GPU acceleration unavailable.' : 'No GPU detected.'}</strong>{' '}
          {gpuStatusMessage}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, margin: '16px 0' }}>
        <div className="hardware-item">
          <span className="hardware-label"><Network size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} />Network</span>
          <span className="hardware-val">↑ {fmt(uploadMbps, 3)} Mbps · ↓ {fmt(downloadMbps, 3)} Mbps</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Latency: {fmt(latency)} ms · Packet loss: {fmt(packetLoss)}%</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Stability: {live?.connectionStability ?? profile.connectionStability ?? 'Unknown'}</span>
        </div>
        <div className="hardware-item">
          <span className="hardware-label"><ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: 5 }} />System & Compatibility</span>
          <span className="hardware-val">{osName} {osVersion}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Worker compatibility: {compatibility}</span>
          {compatibilityDetails.length > 0 && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{compatibilityDetails.join(' · ')}</span>}
        </div>
      </div>

      {joinError && (
        <div style={{ padding: '10px 14px', backgroundColor: 'var(--btn-danger-bg)', color: 'var(--btn-danger-text)', borderRadius: 'var(--radius-md)', fontSize: 13, marginBottom: 16 }}>
          {joinError}
        </div>
      )}

      <div className="resource-grid">
        <ResourceSlider
          id="cpu-slider" title="CPU Compute Contribution" value={cpuPercent} unit="%"
          displayValue={`${cpuPercent}% (${allocatedCores || '—'} logical cores)`}
          min={10} max={100} step={1} inputStep={1}
          subtext={`Detected: ${logicalCores ?? 'unknown'} logical cores; current free CPU capacity: ${fmt(availableCpuPercent)}%`}
          onChange={setCpuPercent} disabled={!live || !logicalCores}
        />
        <ResourceSlider
          id="ram-slider" title="Memory (RAM) Allocation" value={ramGb} unit="GB"
          min={minRamSlider} max={maxRamSlider} step={0.1} inputStep={0.1}
          subtext={`Current available RAM: ${fmt(availableRam)} GB. Select from ${minRamSlider.toFixed(1)} GB to ${maxRamSlider.toFixed(1)} GB, or type a value.`}
          onChange={setRamGb} disabled={!live || maxRamSlider <= 0}
        />
        <ResourceSlider
          id="gpu-slider" title="GPU VRAM Contribution" value={gpuPercent} unit="%"
          displayValue={hasGpu ? `${gpuPercent}% (~${fmt(allocatedVram)} GB VRAM)` : gpuDetected ? 'VRAM unavailable — 0%' : 'No GPU detected — 0%'}
          min={0} max={100} step={1} inputStep={1}
          subtext={hasGpu ? `${fmt(availableVram)} GB currently available VRAM` : gpuStatusMessage}
          onChange={setGpuPercent} disabled={!live || !hasGpu}
        />
        <ResourceSlider
          id="storage-slider" title="Scratch Storage Allocation" value={storageGb} unit="GB"
          min={0} max={maxDiskSlider} step={0.1} inputStep={0.1}
          subtext={`Current available disk space: ${fmt(availableDisk)} GB; values are capped at the detected free space.`}
          onChange={setStorageGb} disabled={!live || maxDiskSlider <= 0}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 24, gap: 12 }}>
        <button type="button" className="btn btn-secondary" onClick={() => navigate('/worker/join')}>
          <ArrowLeft size={16} /><span>Back</span>
        </button>
        <button type="button" className="btn btn-primary" onClick={handleJoin} disabled={isJoining || !hasLiveCapacity}>
          <CheckCircle2 size={16} /><span>{isJoining ? 'Joining Cluster…' : 'Join Project'}</span>
        </button>
      </div>
    </div>
  );
};
