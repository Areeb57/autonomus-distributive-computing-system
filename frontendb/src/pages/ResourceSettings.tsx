import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useApp } from '../context/AppContext';
import { ResourceSlider } from '../components/ResourceSlider';
import { PauseCircle, PlayCircle, RefreshCw, Cpu, MemoryStick, HardDrive, MonitorCog, Wifi, ShieldCheck, AlertTriangle } from 'lucide-react';

type AgentData = Record<string, unknown>;

const PROFILE_KEY = 'adc_agent_profile';
const RESOURCE_SETTINGS_SESSION_KEY = 'adc_resource_settings';
function readSavedProfile(): AgentData | null {
  try {
    const raw = sessionStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed as AgentData : null;
  } catch {
    return null;
  }
}

function num(data: AgentData | null, key: string): number | null {
  const value = data?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function str(data: AgentData | null, key: string, fallback = 'Not detected'): string {
  const value = data?.[key];
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function format(value: number | null, digits = 1): string {
  return value === null ? 'Not reported' : value.toFixed(digits);
}

function hasGpu(profile: AgentData | null, live: AgentData | null): boolean {
  const model = str(profile, 'gpuModel', '').toLowerCase();
  const vendor = str(profile, 'gpuVendor', '').toLowerCase();
  const backend = str(profile, 'gpuComputeBackend', '').toLowerCase();
  const vram = num(profile, 'totalGpuMemoryGB');
  return Boolean(
    (model && !['unknown', 'not detected', 'none', 'no gpu', ''].includes(model)) ||
    (vendor && !['unknown', 'not detected', 'none', ''].includes(vendor)) ||
    (backend && !['unknown', 'not detected', 'none', ''].includes(backend)) ||
    (vram !== null && vram > 0) ||
    (num(live, 'availableGpuMemoryGB') !== null && (num(live, 'availableGpuMemoryGB') ?? 0) > 0)
  );
}

export const ResourceSettings: React.FC = () => {
  const {
    role, resourceSettings, updateResourceSettings,
    masterProject, workerProject
  } = useApp();

  const [profile, setProfile] = useState<AgentData | null>(() => readSavedProfile());
  const [live, setLive] = useState<AgentData | null>(null);
  const [agentConnected, setAgentConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [saveMessage, setSaveMessage] = useState('');

  const saveResourceSettings = useCallback(() => {
    try {
      const saved = {
        ...resourceSettings,
        savedAt: new Date().toISOString()
      };
      sessionStorage.setItem(RESOURCE_SETTINGS_SESSION_KEY, JSON.stringify(saved));
      setSaveMessage(`Saved to this browser session at ${new Date().toLocaleTimeString()}.`);
    } catch {
      setSaveMessage('Could not save settings to sessionStorage. Check your browser storage settings.');
    }
  }, [resourceSettings]);

  const refreshAgentData = useCallback(async () => {
    const freshProfile = readSavedProfile();
    if (freshProfile) setProfile(freshProfile);

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 1800);
    let statusData: AgentData;
    try {
      const baseUrl = import.meta.env.VITE_AGENT_URL || 'http://127.0.0.1:8765';
      const response = await fetch(`${baseUrl}/agent/status`, { cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error('Agent status request failed');
      statusData = await response.json() as AgentData;
    } catch {
      setAgentConnected(false);
      setLive(null);
      return;
    } finally {
      window.clearTimeout(timeout);
    }
    setAgentConnected(true);
    setLive(statusData);
    setLastUpdated(new Date());

    // If the agent service exposes the extended profile, refresh the session cache.
    const permanentFields = [
      'agentId', 'hostname', 'version', 'cpuModel', 'cpuArchitecture',
      'physicalCpuCores', 'logicalCpuCores', 'totalRamGB', 'gpuVendor',
      'gpuModel', 'gpuComputeBackend', 'totalGpuMemoryGB', 'totalDiskGB',
      'osName', 'osVersion', 'workerCompatibilityStatus', 'workerCompatibilityDetails'
    ];
    if (permanentFields.some((key) => statusData[key] !== undefined)) {
      const next: AgentData = { ...(freshProfile ?? {}) };
      for (const key of permanentFields) {
        if (statusData[key] !== undefined) next[key] = statusData[key];
      }
      try {
        sessionStorage.setItem(PROFILE_KEY, JSON.stringify(next));
        setProfile(next);
      } catch {
        // Continue rendering live data even if browser storage is unavailable.
      }
    }
  }, []);

  useEffect(() => {
    void refreshAgentData();
    const timer = window.setInterval(() => void refreshAgentData(), 2000);
    const onStorage = () => setProfile(readSavedProfile());
    window.addEventListener('storage', onStorage);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('storage', onStorage);
    };
  }, [refreshAgentData]);

  const gpuDetected = useMemo(() => hasGpu(profile, live), [profile, live]);
  const cpuModel = str(profile, 'cpuModel', str(live, 'cpuModel'));
  const cpuArchitecture = str(profile, 'cpuArchitecture', str(live, 'cpuArchitecture'));
  const logicalCores = num(profile, 'logicalCpuCores') ?? num(live, 'logicalCpuCores') ?? num(live, 'cpuCores');
  const physicalCores = num(profile, 'physicalCpuCores') ?? num(live, 'physicalCpuCores');
  const totalRam = num(profile, 'totalRamGB') ?? num(live, 'totalRamGB');
  const availableRam = num(live, 'availableRamGB');
  const gpuModel = gpuDetected ? str(profile, 'gpuModel', str(live, 'gpuModel')) : 'No supported GPU detected';
  const gpuVendor = gpuDetected ? str(profile, 'gpuVendor', str(live, 'gpuVendor')) : '—';
  const gpuBackend = gpuDetected ? str(profile, 'gpuComputeBackend', str(live, 'gpuComputeBackend')) : '—';
  const totalVram = gpuDetected ? (num(profile, 'totalGpuMemoryGB') ?? num(live, 'totalGpuMemoryGB')) : null;
  const availableVram = gpuDetected ? num(live, 'availableGpuMemoryGB') : null;
  const totalDisk = num(profile, 'totalDiskGB') ?? num(live, 'totalDiskGB');
  const availableDisk = num(live, 'availableDiskGB');
  const cpuUsage = num(live, 'cpuUtilizationPercent');
  const cpuCapacity = num(live, 'availableCpuCapacityPercent');
  const upload = num(live, 'networkUploadMbps');
  const download = num(live, 'networkDownloadMbps');
  const latency = num(live, 'networkLatencyMs');
  const packetLoss = num(live, 'packetLossPercent');

  const maxRamBudget = Math.max(0, availableRam ?? totalRam ?? 0);
  const maxStorageBudget = Math.max(0, availableDisk ?? totalDisk ?? 0);
  const maxCpuCores = Math.max(0, logicalCores ?? 0);
  const maxGpuVramBudget = Math.max(0, availableVram ?? totalVram ?? 0);
  const cpuBudget = Math.min(100, Math.max(0, resourceSettings.cpuBudgetPercent));
  const cpuCoresBudget = Math.min(maxCpuCores, Math.max(0, resourceSettings.cpuCoresToContribute ?? 0));
  const ramBudget = Math.min(maxRamBudget, Math.max(0, resourceSettings.ramBudgetGb));
  const storageBudget = Math.min(maxStorageBudget, Math.max(0, resourceSettings.storageBudgetGb));
  const gpuBudget = Math.min(100, Math.max(0, resourceSettings.gpuBudgetPercent));
  const gpuVramBudget = Math.min(maxGpuVramBudget, Math.max(0, resourceSettings.gpuVramLimitGb ?? 0));

  const getEffectiveContributionStatus = () => {
    if (!agentConnected || role === 'none') return { label: 'Agent Disconnected', className: 'badge-neutral' };
    if (resourceSettings.globalPaused) return { label: 'Contributions Paused', className: 'badge-paused' };
    if (role === 'master') {
      if (!masterProject || masterProject.status === 'stopped' || masterProject.status === 'ended') return { label: 'Inactive / Idle', className: 'badge-stopped' };
      if (masterProject.status === 'paused') return { label: 'Training Paused', className: 'badge-paused' };
      return { label: 'Active Master Cluster', className: 'badge-active' };
    }
    if (!workerProject || workerProject.status === 'stopped') return { label: 'Not Contributing', className: 'badge-stopped' };
    if (workerProject.status === 'paused') return { label: 'Contribution Paused', className: 'badge-paused' };
    return { label: 'Contributing Compute', className: 'badge-active' };
  };
  const statusInfo = getEffectiveContributionStatus();

  const cardStyle: React.CSSProperties = {
    padding: '16px', border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-lg)', background: 'var(--bg-primary)', minWidth: 0
  };
  const labelStyle: React.CSSProperties = { color: 'var(--text-secondary)', fontSize: '12px', display: 'block', marginBottom: '6px' };
  const valueStyle: React.CSSProperties = { color: 'var(--text-primary)', fontSize: '15px', fontWeight: 600, overflowWrap: 'anywhere' };
  const unavailable = (value: number | null, unit = '') => value === null ? 'Not reported' : `${format(value)}${unit}`;

  return (
    <div className="page-container">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>Resource Settings</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 6 }}>Hardware-aware contribution limits for this machine.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={() => void refreshAgentData()} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '9px 12px', border: '1px solid var(--border-subtle)', borderRadius: 8, background: 'var(--bg-primary)', color: 'var(--text-primary)', cursor: 'pointer' }}>
            <RefreshCw size={15} /> Refresh machine data
          </button>
          <button type="button" onClick={saveResourceSettings} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '9px 14px', border: '1px solid var(--accent, #10a37f)', borderRadius: 8, background: 'var(--accent, #10a37f)', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
            Save
          </button>
        </div>
      </div>

      {saveMessage && <p role="status" aria-live="polite" style={{ color: saveMessage.startsWith('Could not') ? 'var(--status-error-text, #b42318)' : 'var(--text-secondary)', fontSize: 12, marginTop: -12, marginBottom: 16 }}>{saveMessage}</p>}

      <section style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', padding: '16px 20px', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', marginBottom: 24 }}>
        <div>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>ADC agent connection</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
            <span className={`status-dot ${agentConnected ? 'active' : 'disconnected'}`} />
            <strong style={{ fontSize: 14 }}>{agentConnected ? `Connected · ${str(profile, 'hostname', str(live, 'hostname', 'Local machine'))}` : 'Agent not connected'}</strong>
          </div>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{lastUpdated ? `Last response ${lastUpdated.toLocaleTimeString()}` : 'Waiting for agent status'}</span>
        </div>
        <span className={`badge ${statusInfo.className}`}>{statusInfo.label}</span>
      </section>

      {!profile && !agentConnected && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: 14, borderRadius: 10, border: '1px solid var(--border-subtle)', marginBottom: 20 }}>
          <AlertTriangle size={18} />
          <div><strong>No machine profile available</strong><p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 13 }}>Start adc_agent.py and confirm that its status response includes the extended hardware fields. No demo hardware values are shown as real measurements.</p></div>
        </div>
      )}

      <section style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Detected machine information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          <div style={cardStyle}><Cpu size={19} /><span style={labelStyle}>Processor</span><div style={valueStyle}>{cpuModel}</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>{cpuArchitecture} · {physicalCores ?? '—'} physical / {logicalCores ?? '—'} logical cores</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>Current usage: {unavailable(cpuUsage, '%')} · Available capacity: {unavailable(cpuCapacity, '%')}</div></div>
          <div style={cardStyle}><MemoryStick size={19} /><span style={labelStyle}>System memory (RAM)</span><div style={valueStyle}>{unavailable(totalRam, ' GB')} total</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>{unavailable(availableRam, ' GB')} currently available</div></div>
          <div style={cardStyle}><MonitorCog size={19} /><span style={labelStyle}>Graphics processor</span><div style={valueStyle}>{gpuModel}</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>Vendor: {gpuVendor} · Backend: {gpuBackend}</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>VRAM: {unavailable(totalVram, ' GB')} total / {unavailable(availableVram, ' GB')} available</div></div>
          <div style={cardStyle}><HardDrive size={19} /><span style={labelStyle}>Storage</span><div style={valueStyle}>{unavailable(totalDisk, ' GB')} total</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>{unavailable(availableDisk, ' GB')} currently available</div></div>
          <div style={cardStyle}><Wifi size={19} /><span style={labelStyle}>Network</span><div style={valueStyle}>↑ {unavailable(upload, ' Mbps')} · ↓ {unavailable(download, ' Mbps')}</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>Latency: {unavailable(latency, ' ms')} · Packet loss: {unavailable(packetLoss, '%')}</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>Stability: {str(live, 'connectionStability', 'Not reported')}</div></div>
          <div style={cardStyle}><ShieldCheck size={19} /><span style={labelStyle}>Operating system & compatibility</span><div style={valueStyle}>{str(profile, 'osName', str(live, 'osName', str(live, 'platform', 'Not reported')))} {str(profile, 'osVersion', str(live, 'osVersion', ''))}</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>Worker status: {str(profile, 'workerCompatibilityStatus', str(live, 'workerCompatibilityStatus', 'Not reported'))}</div><div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>Agent ID: {str(profile, 'agentId', str(live, 'agentId', 'Not reported'))}</div></div>
        </div>
      </section>

      <section style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap', padding: '16px 20px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', marginBottom: 28, background: resourceSettings.globalPaused ? 'var(--status-paused-bg)' : 'var(--bg-primary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {resourceSettings.globalPaused ? <PauseCircle size={24} color="var(--status-paused-text)" /> : <PlayCircle size={24} color="#10a37f" />}
          <div><div style={{ fontSize: 15, fontWeight: 600 }}>Pause all contributions</div><div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Disable all contribution sliders while paused. The coordinator must enforce this setting for it to affect running jobs.</div></div>
        </div>
        <label className="switch"><input type="checkbox" checked={resourceSettings.globalPaused} onChange={(e) => updateResourceSettings({ globalPaused: e.target.checked })} /><span className="slider-switch" /></label>
      </section>

      <section>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Contribution Budgets</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 0, marginBottom: 14 }}>Choose the maximum capacity this machine may offer. Limits are bounded by detected capacity where available.</p>
        <div className="resource-grid">
          <ResourceSlider id="budget-cpu-cores" title="CPU cores to contribute" value={cpuCoresBudget} unit="cores" min={0} max={Math.max(1, maxCpuCores)} step={1} displayValue={`${cpuCoresBudget} of ${logicalCores ?? '—'} logical cores`} subtext={logicalCores === null ? 'Core count not reported' : 'Maximum logical cores ADC may schedule work on'} onChange={(val) => updateResourceSettings({ cpuCoresToContribute: val })} disabled={resourceSettings.globalPaused || !agentConnected || logicalCores === null} />
          <ResourceSlider id="budget-cpu" title="Maximum CPU utilization" value={cpuBudget} unit="%" min={0} max={100} step={5} subtext={cpuCapacity !== null ? `${format(cpuCapacity)}% capacity currently available` : 'Live CPU capacity not reported'} onChange={(val) => updateResourceSettings({ cpuBudgetPercent: val })} disabled={resourceSettings.globalPaused || !agentConnected || logicalCores === null} />
          <ResourceSlider id="budget-ram" title="Maximum RAM contribution" value={ramBudget} unit="GB" min={0} max={Math.max(1, maxRamBudget)} step={0.5} subtext={availableRam === null ? 'Live available RAM not reported' : `Leaves about ${Math.max(0, availableRam - ramBudget).toFixed(1)} GB of currently available RAM unallocated`} onChange={(val) => updateResourceSettings({ ramBudgetGb: val })} disabled={resourceSettings.globalPaused || !agentConnected || availableRam === null} />
          <ResourceSlider id="budget-gpu" title="Maximum GPU contribution" value={gpuBudget} unit="%" min={0} max={100} step={5} subtext={!gpuDetected ? 'Disabled: no GPU detected' : totalVram === null ? 'GPU detected; total VRAM not reported' : `GPU detected · ${totalVram} GB total VRAM${availableVram !== null ? ` · ${availableVram} GB currently available` : ''}`} onChange={(val) => updateResourceSettings({ gpuBudgetPercent: val })} disabled={resourceSettings.globalPaused || !agentConnected || !gpuDetected || totalVram === null} />
          <ResourceSlider id="budget-gpu-vram" title="GPU VRAM limit" value={gpuVramBudget} unit="GB" min={0} max={Math.max(1, maxGpuVramBudget)} step={0.5} subtext={!gpuDetected ? 'Disabled: no GPU detected' : availableVram === null ? 'Available VRAM not reported' : `${availableVram} GB currently available`} onChange={(val) => updateResourceSettings({ gpuVramLimitGb: val })} disabled={resourceSettings.globalPaused || !agentConnected || !gpuDetected || totalVram === null || availableVram === null} />
          <ResourceSlider id="budget-storage" title="Storage quota" value={storageBudget} unit="GB" min={0} max={Math.max(1, maxStorageBudget)} step={1} subtext={availableDisk === null ? 'Live available disk space not reported' : `Up to ${availableDisk.toFixed(1)} GB currently available for ADC-managed data`} onChange={(val) => updateResourceSettings({ storageBudgetGb: val })} disabled={resourceSettings.globalPaused || !agentConnected || availableDisk === null} />
        </div>
        {!agentConnected && <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 12 }}>Contribution settings are disabled until live agent data is available.</p>}
        {agentConnected && !gpuDetected && <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 12 }}>GPU contribution and GPU VRAM limit are disabled because this agent has not reported a GPU.</p>}
      </section>
    </div>
  );
};
