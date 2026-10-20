import React, { useState } from 'react';
import {
  Cpu,
  HardDrive,
  Zap,
  Database,
  Save,
  RotateCcw,
  AlertCircle,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { defaultContributionSettings, mockAvailableGpus } from '../data/mockHardware';

export const ResourceSettingsPage: React.FC = () => {
  const {
    hardwareProfile,
    contributionSettings,
    updateContributionSettings,
    projects,
  } = useApp();

  // Local editable form state
  const [cpuEnabled, setCpuEnabled] = useState(contributionSettings.cpuEnabled);
  const [cpuCores, setCpuCores] = useState(contributionSettings.cpuCores);
  const [ramBudgetGB, setRamBudgetGB] = useState(contributionSettings.ramBudgetGB);
  const [gpuEnabled, setGpuEnabled] = useState(contributionSettings.gpuEnabled);
  const [selectedGpu, setSelectedGpu] = useState(contributionSettings.selectedGpu);
  const [storageBudgetGB, setStorageBudgetGB] = useState(contributionSettings.storageBudgetGB);
  const [networkPreference, setNetworkPreference] = useState(contributionSettings.networkPreference);
  const [globalPaused, setGlobalPaused] = useState(contributionSettings.globalPaused);

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saveSuccessMessage, setSaveSuccessMessage] = useState(false);

  // Active projects receiving compute from current user
  const projectsContributingTo = projects.filter((p) =>
    p.workers.some((w) => w.isCurrentUser && w.contributionStatus === 'active')
  );

  const handleFieldChange = () => {
    setHasUnsavedChanges(true);
    setSaveSuccessMessage(false);
  };

  const handleSave = () => {
    updateContributionSettings({
      cpuEnabled,
      cpuCores: cpuEnabled ? cpuCores : 0,
      ramBudgetGB,
      gpuEnabled,
      selectedGpu,
      storageBudgetGB,
      networkPreference,
      globalPaused,
    });
    setHasUnsavedChanges(false);
    setSaveSuccessMessage(true);
    setTimeout(() => setSaveSuccessMessage(false), 3500);
  };

  const handleCancel = () => {
    setCpuEnabled(contributionSettings.cpuEnabled);
    setCpuCores(contributionSettings.cpuCores);
    setRamBudgetGB(contributionSettings.ramBudgetGB);
    setGpuEnabled(contributionSettings.gpuEnabled);
    setSelectedGpu(contributionSettings.selectedGpu);
    setStorageBudgetGB(contributionSettings.storageBudgetGB);
    setNetworkPreference(contributionSettings.networkPreference);
    setGlobalPaused(contributionSettings.globalPaused);
    setHasUnsavedChanges(false);
  };

  const handleResetDefaults = () => {
    setCpuEnabled(defaultContributionSettings.cpuEnabled);
    setCpuCores(defaultContributionSettings.cpuCores);
    setRamBudgetGB(defaultContributionSettings.ramBudgetGB);
    setGpuEnabled(defaultContributionSettings.gpuEnabled);
    setSelectedGpu(defaultContributionSettings.selectedGpu);
    setStorageBudgetGB(defaultContributionSettings.storageBudgetGB);
    setNetworkPreference(defaultContributionSettings.networkPreference);
    setGlobalPaused(defaultContributionSettings.globalPaused);
    setHasUnsavedChanges(true);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 26 }} className="animate-fade-in">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 14 }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 6 }}>
            Hardware & Resource Settings
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Manage physical computer capacity, configure volunteer contribution thresholds, and enforce safe limits.
          </p>
        </div>

        {saveSuccessMessage && (
          <div
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--status-online-bg)',
              color: 'var(--status-online)',
              border: '1px solid var(--status-online-border)',
              fontSize: '0.88rem',
              fontWeight: 600,
            }}
          >
            Settings saved and updated across active worker profiles!
          </div>
        )}
      </div>

      {/* SECTION A: Physical Hardware Capacity */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600 }}>1. Local Machine Physical Capacity</h3>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Detected by lightweight worker agent
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 16,
          }}
        >
          <div className="card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-primary)', marginBottom: 8 }}>
              <Cpu size={18} />
              <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>CPU Processor</span>
            </div>
            <strong className="mono" style={{ fontSize: '1.4rem', display: 'block' }}>
              {hardwareProfile.cpuCores} Cores
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
              {hardwareProfile.cpuModel}
            </span>
          </div>

          <div className="card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-cyan)', marginBottom: 8 }}>
              <HardDrive size={18} />
              <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Physical RAM</span>
            </div>
            <strong className="mono" style={{ fontSize: '1.4rem', display: 'block' }}>
              {hardwareProfile.ramTotalGB} GB Total
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
              {hardwareProfile.ramAvailableGB} GB physically uncommitted
            </span>
          </div>

          <div className="card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--status-online)', marginBottom: 8 }}>
              <Zap size={18} />
              <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>GPU Hardware</span>
            </div>
            <strong className="mono" style={{ fontSize: '1.25rem', display: 'block' }}>
              {hardwareProfile.gpuMemoryTotalGB} GB VRAM
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
              {hardwareProfile.gpuModel}
            </span>
          </div>

          <div className="card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--status-paused)', marginBottom: 8 }}>
              <Database size={18} />
              <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Disk Cache</span>
            </div>
            <strong className="mono" style={{ fontSize: '1.4rem', display: 'block' }}>
              {hardwareProfile.diskSpaceAvailableGB} GB Free
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
              High-speed NVMe storage
            </span>
          </div>
        </div>
      </div>

      {/* SECTION B: Contribution Summary Status */}
      <div className="card" style={{ padding: '22px 26px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>
              2. Active Contribution Allocation
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Hardware donated to distributed jobs vs host operating system reservation
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Active Receiving Projects:
            </span>
            <span className="mono" style={{ fontWeight: 700, color: 'var(--accent-primary)', fontSize: '1rem' }}>
              {projectsContributingTo.length}
            </span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
          {/* CPU Meter */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.85rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>CPU Cores Donated:</span>
              <strong className="mono">
                {contributionSettings.cpuEnabled ? contributionSettings.cpuCores : 0} / {hardwareProfile.cpuCores} Cores ({Math.round(((contributionSettings.cpuEnabled ? contributionSettings.cpuCores : 0) / hardwareProfile.cpuCores) * 100)}%)
              </strong>
            </div>
            <div className="progress-bar-container" style={{ height: 8 }}>
              <div
                className="progress-bar-fill"
                style={{
                  width: `${((contributionSettings.cpuEnabled ? contributionSettings.cpuCores : 0) / hardwareProfile.cpuCores) * 100}%`,
                }}
              />
            </div>
          </div>

          {/* RAM Meter */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.85rem' }}>
              <span style={{ color: 'var(--text-secondary)' }}>RAM Donated:</span>
              <strong className="mono">
                {contributionSettings.ramBudgetGB} / {hardwareProfile.ramTotalGB} GB ({Math.round((contributionSettings.ramBudgetGB / hardwareProfile.ramTotalGB) * 100)}%)
              </strong>
            </div>
            <div className="progress-bar-container" style={{ height: 8 }}>
              <div
                className="progress-bar-fill"
                style={{
                  width: `${(contributionSettings.ramBudgetGB / hardwareProfile.ramTotalGB) * 100}%`,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* SECTION C: Editable Settings Form */}
      <div className="card" style={{ padding: '28px 32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
            3. Edit Contribution Limits
          </h3>

          {/* Global Pause Switch */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 500, color: globalPaused ? 'var(--status-paused)' : 'var(--text-secondary)' }}>
              Pause All Contributions Globally
            </span>
            <label className="switch-label">
              <input
                type="checkbox"
                className="switch-input"
                checked={globalPaused}
                onChange={(e) => {
                  setGlobalPaused(e.target.checked);
                  handleFieldChange();
                }}
              />
              <span className="switch-slider" />
            </label>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 24, marginBottom: 24 }}>
          {/* CPU Settings */}
          <div
            style={{
              padding: '20px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <strong style={{ fontSize: '0.95rem' }}>CPU Contribution</strong>
              <label className="switch-label">
                <input
                  type="checkbox"
                  className="switch-input"
                  checked={cpuEnabled}
                  onChange={(e) => {
                    setCpuEnabled(e.target.checked);
                    handleFieldChange();
                  }}
                />
                <span className="switch-slider" />
              </label>
            </div>

            {cpuEnabled ? (
              <div className="slider-container">
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Max Cores:</span>
                  <span className="slider-val-tag">{cpuCores} Cores</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={hardwareProfile.cpuCores}
                  value={cpuCores}
                  onChange={(e) => {
                    setCpuCores(Number(e.target.value));
                    handleFieldChange();
                  }}
                  className="slider-track"
                />
              </div>
            ) : (
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                CPU contribution is currently disabled.
              </span>
            )}
          </div>

          {/* RAM Settings */}
          <div
            style={{
              padding: '20px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <strong style={{ fontSize: '0.95rem', display: 'block', marginBottom: 12 }}>
              RAM Budget
            </strong>
            <div className="slider-container">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Max Allocation:</span>
                <span className="slider-val-tag">{ramBudgetGB} GB</span>
              </div>
              <input
                type="range"
                min={2}
                max={hardwareProfile.ramAvailableGB}
                value={ramBudgetGB}
                onChange={(e) => {
                  setRamBudgetGB(Number(e.target.value));
                  handleFieldChange();
                }}
                className="slider-track"
              />
            </div>
          </div>

          {/* GPU Settings */}
          <div
            style={{
              padding: '20px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <strong style={{ fontSize: '0.95rem' }}>GPU Acceleration</strong>
              <label className="switch-label">
                <input
                  type="checkbox"
                  className="switch-input"
                  checked={gpuEnabled}
                  onChange={(e) => {
                    setGpuEnabled(e.target.checked);
                    handleFieldChange();
                  }}
                />
                <span className="switch-slider" />
              </label>
            </div>

            {gpuEnabled ? (
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Selected GPU Device</label>
                <select
                  className="form-select"
                  value={selectedGpu}
                  onChange={(e) => {
                    setSelectedGpu(e.target.value);
                    handleFieldChange();
                  }}
                >
                  {mockAvailableGpus.map((gpu) => (
                    <option key={gpu} value={gpu}>
                      {gpu}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                GPU acceleration disabled.
              </span>
            )}
          </div>

          {/* Storage & Network Settings */}
          <div
            style={{
              padding: '20px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <strong style={{ fontSize: '0.95rem' }}>Disk & Network</strong>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: 4 }}>
                <span style={{ color: 'var(--text-secondary)' }}>Temporary Disk Budget:</span>
                <span className="mono" style={{ fontWeight: 600 }}>{storageBudgetGB} GB</span>
              </div>
              <input
                type="range"
                min={10}
                max={80}
                step={5}
                value={storageBudgetGB}
                onChange={(e) => {
                  setStorageBudgetGB(Number(e.target.value));
                  handleFieldChange();
                }}
                className="slider-track"
              />
            </div>

            <div>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                Network Sync Preference:
              </span>
              <select
                className="form-select"
                value={networkPreference}
                onChange={(e) => {
                  setNetworkPreference(e.target.value as any);
                  handleFieldChange();
                }}
                style={{ padding: '6px 10px', fontSize: '0.82rem' }}
              >
                <option value="unlimited">Unlimited (Fastest mesh sync)</option>
                <option value="moderate">Moderate (~150 Mbps)</option>
                <option value="saver">Data Saver (~50 Mbps)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Prototype Warning */}
        <div className="alert-box alert-warning">
          <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>Frontend Simulation Notice</strong>
            <p style={{ marginTop: 2, fontSize: '0.84rem' }}>
              These settings configure your simulated node contribution in the frontend state.
              They do not enforce real operating-system cgroups or physical hardware limits.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <button className="btn btn-outline btn-sm" onClick={handleResetDefaults}>
            <RotateCcw size={14} />
            <span>Reset to Defaults</span>
          </button>

          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className="btn btn-secondary"
              onClick={handleCancel}
              disabled={!hasUnsavedChanges}
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSave}
              disabled={!hasUnsavedChanges}
            >
              <Save size={16} />
              <span>Save Changes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
