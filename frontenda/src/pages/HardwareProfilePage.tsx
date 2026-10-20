import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Cpu,
  HardDrive,
  Zap,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  Database,
  Loader2,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Stepper } from '../components/progress/Stepper';
import type { StepItem } from '../components/progress/Stepper';

const profilingSteps = [
  'Inspecting CPU architecture & core topology...',
  'Checking available physical memory & page cache...',
  'Detecting GPU hardware & CUDA acceleration driver...',
  'Checking available GPU video memory (VRAM)...',
  'Querying available local disk caching partition...',
  'Preparing worker node hardware profile...',
];

export const HardwareProfilePage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { hardwareProfile, getProjectById } = useApp();

  const project = projectId ? getProjectById(projectId) : null;

  const [currentProfilingStep, setCurrentProfilingStep] = useState(0);
  const [isProfilingDone, setIsProfilingDone] = useState(false);

  const steps: StepItem[] = [
    { id: 1, title: 'Select Project', subtitle: 'Target Workload' },
    { id: 2, title: 'Worker Agent', subtitle: 'Download & Verification' },
    { id: 3, title: 'Hardware Profiling', subtitle: 'Simulate Specs' },
    { id: 4, title: 'Contribute Resources', subtitle: 'Set Limits & Join' },
  ];

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentProfilingStep((prev) => {
        if (prev < profilingSteps.length - 1) {
          return prev + 1;
        } else {
          clearInterval(timer);
          setIsProfilingDone(true);
          return prev;
        }
      });
    }, 600);

    return () => clearInterval(timer);
  }, []);

  const handleContinue = () => {
    navigate(`/worker-resources/${projectId}`);
  };

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }} className="animate-fade-in">
      {/* Top Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 6 }}>
          Local Hardware Profiling
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          {project ? (
            <span>
              Inspecting local compute budget for project: <strong>{project.name}</strong>
            </span>
          ) : (
            'Simulating hardware diagnostics to establish valid training contribution thresholds.'
          )}
        </p>
      </div>

      {/* Stepper Navigation */}
      <Stepper steps={steps} currentStep={3} />

      {/* Main Diagnostics Card */}
      <div className="card" style={{ padding: '32px 36px', display: 'flex', flexDirection: 'column', gap: 28 }}>
        {!isProfilingDone ? (
          /* Loading Animation & Step Messages */
          <div
            style={{
              padding: '60px 24px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 20,
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: '50%',
                backgroundColor: 'var(--accent-primary-light)',
                color: 'var(--accent-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Loader2 size={32} className="animate-spin" />
            </div>

            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 8 }}>
                Detecting System Hardware
              </h3>
              <p className="mono" style={{ fontSize: '0.92rem', color: 'var(--accent-cyan)' }}>
                {profilingSteps[currentProfilingStep]}
              </p>
            </div>

            <div style={{ width: 280 }} className="progress-bar-container">
              <div
                className="progress-bar-fill"
                style={{
                  width: `${((currentProfilingStep + 1) / profilingSteps.length) * 100}%`,
                  transition: 'width 0.4s ease-out',
                }}
              />
            </div>
          </div>
        ) : (
          /* Illustrative Hardware Profile Result */
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
                  Detected Hardware Profile: Your Computer
                </h3>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  Hardware specs verified and compatible with distributed training
                </span>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  color: 'var(--status-online)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  backgroundColor: 'var(--status-online-bg)',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-full)',
                  border: '1px solid var(--status-online-border)',
                }}
              >
                <CheckCircle2 size={16} />
                <span>Profile Ready</span>
              </div>
            </div>

            {/* Hardware Cards Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 16,
              }}
            >
              {/* CPU Card */}
              <div
                style={{
                  padding: '20px 18px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-input)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--accent-primary)' }}>
                  <Cpu size={22} />
                  <strong style={{ fontSize: '0.95rem' }}>CPU Processor</strong>
                </div>
                <div>
                  <div className="mono" style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                    {hardwareProfile.cpuCores} Cores
                  </div>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    {hardwareProfile.cpuModel}
                  </span>
                </div>
              </div>

              {/* RAM Card */}
              <div
                style={{
                  padding: '20px 18px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-input)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--accent-cyan)' }}>
                  <HardDrive size={22} />
                  <strong style={{ fontSize: '0.95rem' }}>System Memory</strong>
                </div>
                <div>
                  <div className="mono" style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                    {hardwareProfile.ramTotalGB} GB Total
                  </div>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    {hardwareProfile.ramAvailableGB} GB available for volunteer allocation
                  </span>
                </div>
              </div>

              {/* GPU Card */}
              <div
                style={{
                  padding: '20px 18px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-input)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--status-online)' }}>
                  <Zap size={22} />
                  <strong style={{ fontSize: '0.95rem' }}>Graphics Acceleration</strong>
                </div>
                <div>
                  <div className="mono" style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                    {hardwareProfile.gpuModel}
                  </div>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Dedicated VRAM: {hardwareProfile.gpuMemoryTotalGB} GB GDDR6
                  </span>
                </div>
              </div>

              {/* Disk Space Card */}
              <div
                style={{
                  padding: '20px 18px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-input)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--status-paused)' }}>
                  <Database size={22} />
                  <strong style={{ fontSize: '0.95rem' }}>Local Disk Cache</strong>
                </div>
                <div>
                  <div className="mono" style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                    {hardwareProfile.diskSpaceAvailableGB} GB Free
                  </div>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    High-speed NVMe partition for tensor batches
                  </span>
                </div>
              </div>
            </div>

            {/* Prototype Simulation Notice */}
            <div className="alert-box alert-info" style={{ marginBottom: 0 }}>
              <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>Simulation Notice</strong>
                <p style={{ marginTop: 2, fontSize: '0.84rem' }}>
                  Hardware specs are simulated for demonstration. Browsers cannot directly probe
                  physical hardware details without the Python worker agent communicating with the backend.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Bottom Actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 20 }}>
          <button className="btn btn-secondary" onClick={() => navigate(`/worker-setup/${projectId}`)}>
            <ArrowLeft size={16} />
            <span>Back to Agent Setup</span>
          </button>

          <button
            className="btn btn-primary btn-lg"
            onClick={handleContinue}
            disabled={!isProfilingDone}
          >
            <span>Continue to Select Resources</span>
            <ArrowRight size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};
