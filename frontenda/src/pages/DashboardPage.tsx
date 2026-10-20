import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Download,
  Play,
  Globe,
  CheckCircle2,
  Terminal,
  ArrowRight,
  Sparkles,
  Laptop,
  Layers,
  Cpu,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();

  // Interactive demo states for the 3 steps
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [downloaded, setDownloaded] = useState(false);

  const [appRunning, setAppRunning] = useState(false);
  const [appLog, setAppLog] = useState<string[]>([
    'Waiting for ADC App to launch...',
  ]);

  // Simulate Step 1: Download
  const handleDownload = () => {
    if (downloaded) return;
    setDownloading(true);
    setDownloadProgress(15);

    const interval = setInterval(() => {
      setDownloadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setDownloading(false);
          setDownloaded(true);
          return 100;
        }
        return prev + 25;
      });
    }, 280);
  };

  // Simulate Step 2: Run it
  const handleRunApp = () => {
    setAppRunning(true);
    setAppLog([
      '➜ adc-node.exe start --mesh=auto',
      '[ADC-CORE] Initializing distributed client v1.4.2...',
      '[ADC-HW] Detected NVIDIA GeForce RTX 3060 (12 GB VRAM)',
      '[ADC-HW] Detected 16 CPU logical cores, 32 GB RAM',
      '[ADC-NET] Connected to decentralized Ring-AllReduce gossip mesh',
      '[ADC-READY] Local node listening on 127.0.0.1 • Status: ONLINE',
    ]);
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 32 }} className="animate-fade-in">
      {/* Hero Header */}
      <div style={{ textAlign: 'center', padding: '16px 0 8px' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '5px 14px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--accent-primary-light)',
            color: 'var(--accent-primary)',
            fontSize: '0.82rem',
            fontWeight: 600,
            marginBottom: 16,
          }}
        >
          <Sparkles size={14} />
          Quick Start Process
        </div>

        <h1
          style={{
            fontSize: '2.4rem',
            fontWeight: 800,
            letterSpacing: '-0.03em',
            lineHeight: 1.2,
            marginBottom: 12,
          }}
        >
          Start Autonomous Distributed AI Training
        </h1>

        <p
          style={{
            fontSize: '1.1rem',
            color: 'var(--text-secondary)',
            maxWidth: 620,
            margin: '0 auto',
            lineHeight: 1.6,
          }}
        >
          Follow these 3 simple steps to get the client running on your machine and connect to the decentralized training network.
        </p>
      </div>

      {/* 3-Step Process Container */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* =========================================================================
            STEP 1: Download the ADC App
           ========================================================================= */}
        <div
          className="card card-glow"
          style={{
            padding: '32px 36px',
            display: 'grid',
            gridTemplateColumns: '70px 1fr',
            gap: 24,
            alignItems: 'flex-start',
            borderColor: downloaded ? 'var(--status-online)' : 'var(--border-subtle)',
          }}
        >
          {/* Step Number Circle */}
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: downloaded
                ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                : 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              fontWeight: 800,
              boxShadow: downloaded
                ? '0 0 20px rgba(16, 185, 129, 0.4)'
                : '0 0 20px rgba(99, 102, 241, 0.4)',
              flexShrink: 0,
            }}
          >
            {downloaded ? <CheckCircle2 size={32} /> : '1'}
          </div>

          {/* Content */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <span
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    color: 'var(--accent-primary)',
                    display: 'block',
                    marginBottom: 2,
                  }}
                >
                  Step 1
                </span>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>
                  Download the ADC App
                </h2>
              </div>

              {downloaded && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--status-online)',
                    backgroundColor: 'var(--status-online-bg)',
                    padding: '4px 12px',
                    borderRadius: 'var(--radius-full)',
                    border: '1px solid var(--status-online-border)',
                  }}
                >
                  <CheckCircle2 size={14} />
                  Downloaded & Ready
                </span>
              )}
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.96rem', lineHeight: 1.6 }}>
              Download the lightweight Autonomous Distributed Compute (ADC) desktop client installer.
              It packages the sandboxed Python execution runtime, CUDA acceleration hooks, and peer-to-peer gossip client.
            </p>

            {/* Action & OS Download Options */}
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 14, marginTop: 4 }}>
              <button
                className={`btn ${downloaded ? 'btn-secondary' : 'btn-primary'} btn-lg`}
                onClick={handleDownload}
                disabled={downloading}
                style={{ padding: '12px 26px' }}
              >
                <Download size={18} />
                <span>
                  {downloaded
                    ? 'Downloaded (ADC-Installer-v1.4.2.exe)'
                    : downloading
                    ? `Downloading... ${downloadProgress}%`
                    : 'Download ADC App for Windows'}
                </span>
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                <Laptop size={14} />
                <span>Also available for macOS (Apple Silicon & Intel) and Linux (.deb / .tar.gz)</span>
              </div>
            </div>

            {/* Simulated Download Progress Bar */}
            {downloading && (
              <div style={{ marginTop: 4 }}>
                <div className="progress-bar-container" style={{ height: 8 }}>
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${downloadProgress}%`, transition: 'width 0.25s ease-out' }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* =========================================================================
            STEP 2: Run It
           ========================================================================= */}
        <div
          className="card card-glow"
          style={{
            padding: '32px 36px',
            display: 'grid',
            gridTemplateColumns: '70px 1fr',
            gap: 24,
            alignItems: 'flex-start',
            borderColor: appRunning ? 'var(--status-online)' : 'var(--border-subtle)',
          }}
        >
          {/* Step Number Circle */}
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: appRunning
                ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                : 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              fontWeight: 800,
              boxShadow: appRunning
                ? '0 0 20px rgba(16, 185, 129, 0.4)'
                : '0 0 20px rgba(6, 182, 212, 0.4)',
              flexShrink: 0,
            }}
          >
            {appRunning ? <CheckCircle2 size={32} /> : '2'}
          </div>

          {/* Content */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <span
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    color: 'var(--accent-cyan)',
                    display: 'block',
                    marginBottom: 2,
                  }}
                >
                  Step 2
                </span>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>
                  Run the ADC App
                </h2>
              </div>

              {appRunning ? (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    color: 'var(--status-online)',
                    backgroundColor: 'var(--status-online-bg)',
                    padding: '4px 12px',
                    borderRadius: 'var(--radius-full)',
                    border: '1px solid var(--status-online-border)',
                  }}
                >
                  <span className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--status-online)' }} />
                  Node Daemon Active
                </span>
              ) : (
                <span
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--text-muted)',
                    backgroundColor: 'var(--bg-input)',
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-full)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  Daemon Not Running
                </span>
              )}
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.96rem', lineHeight: 1.6 }}>
              Launch the downloaded app or run it from your command line. The client inspects your hardware,
              registers your GPU/CPU capabilities, and safely listens for distributed AI gradient jobs.
            </p>

            {/* Simulated Run Trigger Button */}
            <div>
              {!appRunning ? (
                <button className="btn btn-primary btn-lg" onClick={handleRunApp} style={{ padding: '12px 26px' }}>
                  <Play size={18} />
                  <span>Launch / Run ADC App</span>
                </button>
              ) : (
                <button className="btn btn-secondary btn-sm" onClick={handleRunApp}>
                  <CheckCircle2 size={16} color="var(--status-online)" />
                  <span>Restart / Refresh Daemon</span>
                </button>
              )}
            </div>

            {/* Terminal Output Preview */}
            <div
              style={{
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '12px 16px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.82rem',
                color: appRunning ? 'var(--status-online)' : 'var(--text-muted)',
                lineHeight: 1.5,
                maxHeight: 150,
                overflowY: 'auto',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                <Terminal size={14} />
                <span>ADC Node Terminal Feed:</span>
              </div>
              {appLog.map((line, idx) => (
                <div key={idx} style={{ marginTop: 2 }}>{line}</div>
              ))}
            </div>
          </div>
        </div>

        {/* =========================================================================
            STEP 3: Come to Website
           ========================================================================= */}
        <div
          className="card card-glow"
          style={{
            padding: '32px 36px',
            display: 'grid',
            gridTemplateColumns: '70px 1fr',
            gap: 24,
            alignItems: 'flex-start',
            borderColor: appRunning ? 'var(--accent-primary)' : 'var(--border-subtle)',
          }}
        >
          {/* Step Number Circle */}
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              fontWeight: 800,
              boxShadow: '0 0 20px rgba(139, 92, 246, 0.4)',
              flexShrink: 0,
            }}
          >
            3
          </div>

          {/* Content */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <span
                style={{
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--accent-primary)',
                  display: 'block',
                  marginBottom: 2,
                }}
              >
                Step 3
              </span>
              <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>
                Come to Website
              </h2>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.96rem', lineHeight: 1.6 }}>
              With your client running, you are all set! Come right here to this website to discover active
              training runs, volunteer your computer as a <strong>Worker</strong>, or publish your own model
              and dataset as a <strong>Master</strong> coordinator.
            </p>

            {/* Direct Action Choices */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 16,
                marginTop: 8,
              }}
            >
              {/* Option A: Discover Projects as Worker */}
              <div
                className="card card-interactive"
                onClick={() => navigate('/projects')}
                style={{
                  padding: '20px 22px',
                  backgroundColor: 'var(--bg-card-elevated)',
                  border: '1px solid var(--border-medium)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 14,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-cyan)', marginBottom: 8 }}>
                    <Layers size={20} />
                    <strong style={{ fontSize: '1.05rem' }}>Browse Projects (Worker)</strong>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    Join volunteer pools, select your CPU/RAM/GPU budget, and contribute compute cycles.
                  </p>
                </div>

                <button className="btn btn-secondary btn-sm" style={{ width: '100%', justifyContent: 'space-between' }}>
                  <span>Explore Projects</span>
                  <ArrowRight size={15} />
                </button>
              </div>

              {/* Option B: Create Project as Master */}
              <div
                className="card card-interactive"
                onClick={() => navigate('/create-project')}
                style={{
                  padding: '20px 22px',
                  backgroundColor: 'var(--bg-card-elevated)',
                  border: '1px solid var(--border-medium)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 14,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-primary)', marginBottom: 8 }}>
                    <Globe size={20} />
                    <strong style={{ fontSize: '1.05rem' }}>Start Project (Master)</strong>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    Upload your dataset and model architecture to coordinate distributed training across volunteer nodes.
                  </p>
                </div>

                <button className="btn btn-primary btn-sm" style={{ width: '100%', justifyContent: 'space-between' }}>
                  <span>Create New Project</span>
                  <ArrowRight size={15} />
                </button>
              </div>

              {/* Option C: Resource Settings */}
              <div
                className="card card-interactive"
                onClick={() => navigate('/resources')}
                style={{
                  padding: '20px 22px',
                  backgroundColor: 'var(--bg-card-elevated)',
                  border: '1px solid var(--border-medium)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 14,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--status-online)', marginBottom: 8 }}>
                    <Cpu size={20} />
                    <strong style={{ fontSize: '1.05rem' }}>Resource Settings</strong>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    Configure maximum CPU cores, RAM ceilings, and GPU hardware allocation budgets.
                  </p>
                </div>

                <button className="btn btn-secondary btn-sm" style={{ width: '100%', justifyContent: 'space-between' }}>
                  <span>Configure Limits</span>
                  <ArrowRight size={15} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
