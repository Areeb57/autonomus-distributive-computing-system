import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Cpu,
  HardDrive,
  Zap,
  ArrowLeft,
  Sparkles,
  AlertCircle,
  Database,
  Wifi,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Stepper } from '../components/progress/Stepper';
import type { StepItem } from '../components/progress/Stepper';
import { mockAvailableGpus } from '../data/mockHardware';

export const ResourceSelectionPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const {
    hardwareProfile,
    contributionSettings,
    updateContributionSettings,
    joinProjectAsWorker,
    getProjectById,
  } = useApp();

  const project = projectId ? getProjectById(projectId) : null;

  // Local form state initialized from user's preferred settings
  const [cpuEnabled, setCpuEnabled] = useState(contributionSettings.cpuEnabled);
  const [cpuCores, setCpuCores] = useState(contributionSettings.cpuCores);
  const [ramBudgetGB, setRamBudgetGB] = useState(contributionSettings.ramBudgetGB);
  const [gpuEnabled, setGpuEnabled] = useState(contributionSettings.gpuEnabled);
  const [selectedGpu, setSelectedGpu] = useState(contributionSettings.selectedGpu);
  const [storageBudgetGB, setStorageBudgetGB] = useState(contributionSettings.storageBudgetGB);
  const [networkPreference, setNetworkPreference] = useState(contributionSettings.networkPreference);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const steps: StepItem[] = [
    { id: 1, title: 'Select Project', subtitle: 'Target Workload' },
    { id: 2, title: 'Worker Agent', subtitle: 'Download & Verification' },
    { id: 3, title: 'Hardware Profiling', subtitle: 'Simulate Specs' },
    { id: 4, title: 'Contribute Resources', subtitle: 'Set Limits & Join' },
  ];

  const handleJoinProject = () => {
    if (!projectId) return;

    setIsSubmitting(true);

    const newSettings = {
      cpuEnabled,
      cpuCores: cpuEnabled ? cpuCores : 0,
      ramBudgetGB,
      gpuEnabled,
      selectedGpu,
      storageBudgetGB,
      networkPreference,
      globalPaused: false,
    };

    // Save contribution settings
    updateContributionSettings(newSettings);

    setTimeout(() => {
      // Join project as worker node
      joinProjectAsWorker(projectId, newSettings);
      setIsSubmitting(false);
      navigate(`/projects/${projectId}`);
    }, 450);
  };

  return (
    <div style={{ maxWidth: 880, margin: '0 auto' }} className="animate-fade-in">
      {/* Top Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 6 }}>
          Configure Contributed Resources
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          {project ? (
            <span>
              Define the hardware budget to donate to: <strong>{project.name}</strong>
            </span>
          ) : (
            'Define maximum CPU, RAM, and GPU capacities safe to allocate to the cluster.'
          )}
        </p>
      </div>

      {/* Stepper Navigation */}
      <Stepper steps={steps} currentStep={4} />

      {/* Settings Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 24, marginBottom: 28 }}>
        {/* Left Column: Sliders & Toggles */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* CPU Contribution */}
          <div className="card" style={{ padding: '22px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Cpu size={20} color="var(--accent-primary)" />
                <div>
                  <strong style={{ fontSize: '1rem', display: 'block' }}>CPU Contribution</strong>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Total available: {hardwareProfile.cpuCores} cores
                  </span>
                </div>
              </div>

              <label className="switch-label">
                <input
                  type="checkbox"
                  className="switch-input"
                  checked={cpuEnabled}
                  onChange={(e) => setCpuEnabled(e.target.checked)}
                />
                <span className="switch-slider" />
              </label>
            </div>

            {cpuEnabled && (
              <div className="slider-container" style={{ marginTop: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    Allocated CPU Cores:
                  </span>
                  <span className="slider-val-tag">
                    {cpuCores} of {hardwareProfile.cpuCores} Cores ({Math.round((cpuCores / hardwareProfile.cpuCores) * 100)}%)
                  </span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={hardwareProfile.cpuCores}
                  value={cpuCores}
                  onChange={(e) => setCpuCores(Number(e.target.value))}
                  className="slider-track"
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Leaves {hardwareProfile.cpuCores - cpuCores} cores dedicated to your host OS and background tasks.
                </span>
              </div>
            )}
          </div>

          {/* RAM Contribution */}
          <div className="card" style={{ padding: '22px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <HardDrive size={20} color="var(--accent-cyan)" />
                <div>
                  <strong style={{ fontSize: '1rem', display: 'block' }}>Memory (RAM) Budget</strong>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Total physical RAM: {hardwareProfile.ramTotalGB} GB ({hardwareProfile.ramAvailableGB} GB free)
                  </span>
                </div>
              </div>
            </div>

            <div className="slider-container">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  Allocated RAM Budget:
                </span>
                <span className="slider-val-tag">
                  {ramBudgetGB} GB of {hardwareProfile.ramTotalGB} GB ({Math.round((ramBudgetGB / hardwareProfile.ramTotalGB) * 100)}%)
                </span>
              </div>
              <input
                type="range"
                min={2}
                max={hardwareProfile.ramAvailableGB}
                value={ramBudgetGB}
                onChange={(e) => setRamBudgetGB(Number(e.target.value))}
                className="slider-track"
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Guaranteed headroom: {hardwareProfile.ramTotalGB - ramBudgetGB} GB kept free for your applications.
              </span>
            </div>
          </div>

          {/* GPU Contribution */}
          <div className="card" style={{ padding: '22px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Zap size={20} color={gpuEnabled ? 'var(--status-online)' : 'var(--text-muted)'} />
                <div>
                  <strong style={{ fontSize: '1rem', display: 'block' }}>GPU Acceleration</strong>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    CUDA / Tensor Core computation
                  </span>
                </div>
              </div>

              <label className="switch-label">
                <input
                  type="checkbox"
                  className="switch-input"
                  checked={gpuEnabled}
                  onChange={(e) => setGpuEnabled(e.target.checked)}
                />
                <span className="switch-slider" />
              </label>
            </div>

            {gpuEnabled ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Select GPU Device</label>
                  <select
                    className="form-select"
                    value={selectedGpu}
                    onChange={(e) => setSelectedGpu(e.target.value)}
                  >
                    {mockAvailableGpus.map((gpu) => (
                      <option key={gpu} value={gpu}>
                        {gpu}
                      </option>
                    ))}
                  </select>
                </div>
                <div
                  style={{
                    fontSize: '0.74rem',
                    color: 'var(--text-muted)',
                    backgroundColor: 'var(--bg-input)',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <span style={{ display: 'block', color: 'var(--status-paused)', fontWeight: 600, marginBottom: 2 }}>
                    VRAM Limit Notice:
                  </span>
                  GPU utilization percentage limits cannot be hard-guaranteed on all operating systems.
                  The agent allocates VRAM tensors strictly within model checkpoint bounds.
                </div>
              </div>
            ) : (
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                GPU disabled. Worker will participate in CPU-only AllReduce operations.
              </span>
            )}
          </div>

          {/* Storage & Network */}
          <div className="card" style={{ padding: '22px 24px' }}>
            <h4 style={{ fontSize: '0.98rem', fontWeight: 600, marginBottom: 14 }}>
              Storage & Network Preferences
            </h4>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  <Database size={15} color="var(--accent-primary)" />
                  <span>Temporary Disk Budget:</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input
                    type="range"
                    min={10}
                    max={80}
                    step={5}
                    value={storageBudgetGB}
                    onChange={(e) => setStorageBudgetGB(Number(e.target.value))}
                    className="slider-track"
                  />
                  <span className="mono" style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                    {storageBudgetGB} GB
                  </span>
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  <Wifi size={15} color="var(--accent-cyan)" />
                  <span>Network Bandwidth:</span>
                </div>
                <select
                  className="form-select"
                  value={networkPreference}
                  onChange={(e) => setNetworkPreference(e.target.value as any)}
                  style={{ padding: '6px 10px', fontSize: '0.82rem' }}
                >
                  <option value="unlimited">Unlimited (Fastest sync)</option>
                  <option value="moderate">Moderate (~150 Mbps)</option>
                  <option value="saver">Data Saver (~50 Mbps)</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Your Contribution Summary Box */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div
            className="card card-glow"
            style={{
              padding: '28px 26px',
              backgroundColor: 'var(--bg-card-elevated)',
              border: '1px solid var(--accent-primary)',
              display: 'flex',
              flexDirection: 'column',
              gap: 20,
            }}
          >
            <div>
              <span
                style={{
                  fontSize: '0.74rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--accent-primary)',
                  fontWeight: 700,
                  display: 'block',
                  marginBottom: 4,
                }}
              >
                Volunteer Configuration
              </span>
              <h3 style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                Your Contribution Summary
              </h3>
            </div>

            {/* Contribution Breakdown */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 14px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.88rem' }}>
                  <Cpu size={16} color="var(--accent-primary)" />
                  <span>CPU Cores</span>
                </div>
                <strong className="mono" style={{ color: 'var(--text-primary)' }}>
                  {cpuEnabled ? `${cpuCores} of ${hardwareProfile.cpuCores} Cores` : 'Disabled'}
                </strong>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 14px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.88rem' }}>
                  <HardDrive size={16} color="var(--accent-cyan)" />
                  <span>RAM Budget</span>
                </div>
                <strong className="mono" style={{ color: 'var(--text-primary)' }}>
                  {ramBudgetGB} GB of {hardwareProfile.ramTotalGB} GB System
                </strong>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 14px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.88rem' }}>
                  <Zap size={16} color={gpuEnabled ? 'var(--status-online)' : 'var(--text-muted)'} />
                  <span>GPU Acceleration</span>
                </div>
                <strong
                  className="mono"
                  style={{
                    color: gpuEnabled ? 'var(--status-online)' : 'var(--text-muted)',
                    textAlign: 'right',
                    fontSize: '0.82rem',
                    maxWidth: 160,
                  }}
                >
                  {gpuEnabled ? selectedGpu : 'Disabled'}
                </strong>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 14px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.88rem' }}>
                  <Database size={16} color="var(--status-paused)" />
                  <span>Disk Cache Limit</span>
                </div>
                <strong className="mono" style={{ color: 'var(--text-primary)' }}>
                  {storageBudgetGB} GB Temporary
                </strong>
              </div>
            </div>

            {/* Simulation Notice */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                fontSize: '0.78rem',
                color: 'var(--text-muted)',
                lineHeight: 1.45,
                borderTop: '1px solid var(--border-subtle)',
                paddingTop: 14,
              }}
            >
              <AlertCircle size={15} color="var(--text-muted)" style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                These settings are simulated in the frontend. No actual hardware resources are
                locked or consumed on your physical machine.
              </span>
            </div>

            {/* Prominent Action Button */}
            <button
              className="btn btn-primary btn-lg"
              style={{ width: '100%', padding: '16px 20px', marginTop: 8 }}
              onClick={handleJoinProject}
              disabled={isSubmitting}
            >
              <Sparkles size={18} />
              <span>{isSubmitting ? 'Connecting Node to Mesh...' : 'Join Project and Start Contributing'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Back Button */}
      <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
        <button className="btn btn-secondary" onClick={() => navigate(`/worker-hardware/${projectId}`)}>
          <ArrowLeft size={16} />
          <span>Back to Hardware Profile</span>
        </button>
      </div>
    </div>
  );
};
