import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Download,
  Terminal,
  ShieldAlert,
  CheckCircle2,
  Cpu,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  AlertTriangle,
  FileCode,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Stepper } from '../components/progress/Stepper';
import type { StepItem } from '../components/progress/Stepper';

export const WorkerSetupPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { getProjectById } = useApp();

  const project = projectId ? getProjectById(projectId) : null;

  const [downloadProgress, setDownloadProgress] = useState<number | null>(null);
  const [downloadState, setDownloadState] = useState<'idle' | 'downloading' | 'ready'>('idle');

  const steps: StepItem[] = [
    { id: 1, title: 'Select Project', subtitle: 'Target Workload' },
    { id: 2, title: 'Worker Agent', subtitle: 'Download & Verification' },
    { id: 3, title: 'Hardware Profiling', subtitle: 'Simulate Specs' },
    { id: 4, title: 'Contribute Resources', subtitle: 'Set Limits & Join' },
  ];

  // Start simulated download
  const handleDownloadAgent = () => {
    setDownloadState('downloading');
    setDownloadProgress(10);

    const interval = setInterval(() => {
      setDownloadProgress((prev) => {
        if (prev === null) return 10;
        if (prev >= 100) {
          clearInterval(interval);
          setDownloadState('ready');
          return 100;
        }
        return prev + 25;
      });
    }, 350);
  };

  const handleContinue = () => {
    navigate(`/worker-hardware/${projectId}`);
  };

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }} className="animate-fade-in">
      {/* Top Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 6 }}>
          Worker Node Setup
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          {project ? (
            <span>
              Preparing to contribute compute to: <strong>{project.name}</strong>
            </span>
          ) : (
            'Configure your local computer to execute distributed training batches.'
          )}
        </p>
      </div>

      {/* Stepper Navigation */}
      <Stepper steps={steps} currentStep={2} />

      {/* Main Setup Card */}
      <div className="card" style={{ padding: '32px 36px', display: 'flex', flexDirection: 'column', gap: 28 }}>
        {/* What the Agent does */}
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 12 }}>
            Lightweight Python Worker Agent
          </h3>
          <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            The distributed training cluster relies on a sandboxed volunteer agent. The agent inspects
            your computer’s CPU, RAM, and GPU capabilities, enforces the resource limits you set,
            and executes only approved cryptographic model workloads.
          </p>
        </div>

        {/* Feature Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
          <div
            style={{
              padding: 16,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-primary)', marginBottom: 8 }}>
              <Cpu size={18} />
              <strong style={{ fontSize: '0.9rem' }}>Hardware Budgeting</strong>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Strictly enforces CPU thread counts, RAM bounds, and VRAM ceilings defined by you.
            </p>
          </div>

          <div
            style={{
              padding: 16,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-cyan)', marginBottom: 8 }}>
              <FileCode size={18} />
              <strong style={{ fontSize: '0.9rem' }}>Zero-Privilege Sandbox</strong>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Executes isolated tensor calculations without filesystem access to personal files.
            </p>
          </div>

          <div
            style={{
              padding: 16,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--status-online)', marginBottom: 8 }}>
              <Sparkles size={18} />
              <strong style={{ fontSize: '0.9rem' }}>Ring-AllReduce Gossip</strong>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Synchronizes backward-pass gradients directly with neighbor nodes with low latency.
            </p>
          </div>
        </div>

        {/* Security Notice */}
        <div className="alert-box alert-warning">
          <ShieldAlert size={20} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>Security & Privacy Notice</strong>
            <p style={{ marginTop: 2, fontSize: '0.84rem' }}>
              The agent runs on your local machine. You retain full control over pause, resume, and
              instant withdrawal at any point during cluster execution.
            </p>
          </div>
        </div>

        {/* Download & Installation Section */}
        <div
          style={{
            padding: 24,
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'var(--bg-input)',
            border: '1px solid var(--border-medium)',
            display: 'flex',
            flexDirection: 'column',
            gap: 18,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <strong style={{ fontSize: '1rem', display: 'block' }}>
                Python Worker Agent Package (v1.4.2)
              </strong>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Includes PyTorch CUDA bindings, telemetry daemon, and Ring-AllReduce client (18.4 MB)
              </span>
            </div>

            {downloadState === 'idle' && (
              <button className="btn btn-primary" onClick={handleDownloadAgent}>
                <Download size={16} />
                <span>Download Worker Agent</span>
              </button>
            )}

            {downloadState === 'downloading' && (
              <button className="btn btn-secondary" disabled>
                <span className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--accent-primary)' }} />
                <span>Downloading Agent... {downloadProgress}%</span>
              </button>
            )}

            {downloadState === 'ready' && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  color: 'var(--status-online)',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                }}
              >
                <CheckCircle2 size={18} />
                <span>Agent Verified & Ready</span>
              </div>
            )}
          </div>

          {/* Download progress bar */}
          {downloadState === 'downloading' && (
            <div className="progress-bar-container" style={{ height: 8 }}>
              <div
                className="progress-bar-fill"
                style={{ width: `${downloadProgress}%`, transition: 'width 0.3s ease-out' }}
              />
            </div>
          )}

          {/* CLI Instructions */}
          <div style={{ marginTop: 4 }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Quick-Start Terminal Command (Optional for manual daemon run):
            </span>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                backgroundColor: 'var(--bg-app)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.82rem',
                color: 'var(--text-primary)',
              }}
            >
              <span>pip install adc-worker-agent && adc-worker start --mesh=join</span>
              <Terminal size={15} color="var(--text-muted)" />
            </div>
          </div>
        </div>

        {/* Demo Disclaimer */}
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <AlertTriangle size={14} color="var(--status-paused)" />
          <span>
            <strong>Simulation Note:</strong> In this frontend prototype, agent installation is
            simulated in-browser. No files are executed on your operating system.
          </span>
        </div>

        {/* Navigation Actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: 20 }}>
          <button className="btn btn-secondary" onClick={() => navigate('/projects')}>
            <ArrowLeft size={16} />
            <span>Back to Discovery</span>
          </button>

          <button
            className="btn btn-primary btn-lg"
            onClick={handleContinue}
            disabled={downloadState === 'downloading'}
          >
            <span>Continue to Hardware Profiling</span>
            <ArrowRight size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};
