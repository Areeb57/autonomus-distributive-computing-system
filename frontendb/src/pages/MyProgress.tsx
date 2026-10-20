import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { ProjectCode } from '../components/ProjectCode';
import { ProgressMetrics } from '../components/ProgressMetrics';
import { WorkerCard } from '../components/WorkerCard';
import { ConfirmDialog } from '../components/ConfirmDialog';
import {
  Pause,
  Play,
  Square,
  Trash2,
  Cpu,
  Server,
  Activity,
  Layers,
  CheckCircle
} from 'lucide-react';

export const MyProgress: React.FC = () => {
  const navigate = useNavigate();
  const {
    role,
    masterProject,
    workerProject,
    updateMasterControls,
    updateWorkerControls,
    resourceSettings
  } = useApp();

  // Dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText: string;
    isDestructive: boolean;
    action: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    confirmText: '',
    isDestructive: false,
    action: () => {}
  });

  const closeDialog = () => {
    setConfirmDialog((prev) => ({ ...prev, isOpen: false }));
  };

  // --------------------------------------------------------------------------
  // MASTER PROGRESS VIEW
  // --------------------------------------------------------------------------
  if (role === 'master') {
    if (!masterProject || masterProject.status === 'ended') {
      return (
        <div className="page-container centered">
          <h2 style={{ marginBottom: '8px' }}>No Active Master Project</h2>
          <p style={{ marginBottom: '20px', color: 'var(--text-secondary)' }}>
            You do not currently have a training project running.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/master/setup')}
          >
            Create New Project
          </button>
        </div>
      );
    }

    const isGloballyPaused = resourceSettings.globalPaused;
    const isPaused = masterProject.status === 'paused' || isGloballyPaused;
    const isStopped = masterProject.status === 'stopped';

    const handleMasterPauseResume = () => {
      if (isPaused) {
        updateMasterControls('resume');
      } else {
        updateMasterControls('pause');
      }
    };

    const handleMasterStop = () => {
      setConfirmDialog({
        isOpen: true,
        title: 'Stop Training?',
        message:
          'Stopping training will freeze model weights at the current step and halt all cluster computation. This can be resumed later.',
        confirmText: 'Stop Training',
        isDestructive: true,
        action: () => {
          updateMasterControls('stop');
          closeDialog();
        }
      });
    };

    const handleMasterEnd = () => {
      setConfirmDialog({
        isOpen: true,
        title: 'End Project Permanently?',
        message:
          'This action will permanently terminate the training cluster, dismiss connected workers, and delete the project code. This action cannot be undone.',
        confirmText: 'End Project',
        isDestructive: true,
        action: () => {
          updateMasterControls('end');
          closeDialog();
          navigate('/');
        }
      });
    };

    return (
      <div className="page-container wide">
        {/* Header with Project Title & Code */}
        <div className="progress-header">
          <div className="project-meta">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '22px' }}>{masterProject.name}</h1>
              <span
                className={`badge ${
                  isStopped
                    ? 'badge-stopped'
                    : isPaused
                    ? 'badge-paused'
                    : 'badge-active'
                }`}
              >
                {isGloballyPaused
                  ? 'Globally Paused'
                  : isStopped
                  ? 'Stopped'
                  : isPaused
                  ? 'Paused'
                  : 'Training Active'}
              </span>
            </div>
            {masterProject.description && (
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                {masterProject.description}
              </p>
            )}
          </div>

          <ProjectCode code={masterProject.projectCode} label="Cluster Project Code" />
        </div>

        {/* Training Metrics */}
        <ProgressMetrics
          progress={masterProject.progress}
          currentStep={masterProject.currentStep}
          totalSteps={masterProject.totalSteps}
          loss={masterProject.loss}
          speed={isPaused || isStopped ? '0 samples/s' : masterProject.speed}
          elapsedSeconds={masterProject.elapsedSeconds}
          estimatedRemainingSeconds={
            isPaused || isStopped ? undefined : masterProject.estimatedRemainingSeconds
          }
        />

        {/* Master Controls */}
        <div className="controls-bar">
          <span style={{ fontSize: '13px', fontWeight: 600, marginRight: '6px' }}>
            Master Controls:
          </span>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleMasterPauseResume}
            disabled={isStopped || isGloballyPaused}
          >
            {isPaused ? (
              <>
                <Play size={15} fill="currentColor" />
                <span>Resume Training</span>
              </>
            ) : (
              <>
                <Pause size={15} />
                <span>Pause Training</span>
              </>
            )}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleMasterStop}
            disabled={isStopped}
          >
            <Square size={15} />
            <span>Stop Training</span>
          </button>

          <button
            type="button"
            className="btn btn-danger"
            onClick={handleMasterEnd}
          >
            <Trash2 size={15} />
            <span>End Project</span>
          </button>
        </div>

        {/* Connected Workers Section */}
        <div className="workers-section">
          <div className="workers-section-title">
            <span>Connected Workers ({masterProject.workers.length})</span>
            <small style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
              Simulated Telemetry • Auto-synced
            </small>
          </div>

          <div className="workers-grid">
            {masterProject.workers.map((worker) => (
              <WorkerCard key={worker.id} worker={worker} />
            ))}
          </div>
        </div>

        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          title={confirmDialog.title}
          message={confirmDialog.message}
          confirmText={confirmDialog.confirmText}
          isDestructive={confirmDialog.isDestructive}
          onConfirm={confirmDialog.action}
          onCancel={closeDialog}
        />
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // WORKER PROGRESS VIEW
  // --------------------------------------------------------------------------
  if (role === 'worker') {
    if (!workerProject || workerProject.status === 'stopped') {
      return (
        <div className="page-container centered">
          <h2 style={{ marginBottom: '8px' }}>No Active Project Contribution</h2>
          <p style={{ marginBottom: '20px', color: 'var(--text-secondary)' }}>
            You are not currently contributing resources to any project cluster.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/worker/join')}
          >
            Join a Project
          </button>
        </div>
      );
    }

    const isGloballyPaused = resourceSettings.globalPaused;
    const isPaused = workerProject.status === 'paused' || isGloballyPaused;

    const handleWorkerPauseResume = () => {
      if (isPaused) {
        updateWorkerControls('resume');
      } else {
        updateWorkerControls('pause');
      }
    };

    const handleWorkerStop = () => {
      setConfirmDialog({
        isOpen: true,
        title: 'Stop My Contribution?',
        message:
          'Stopping your contribution will disconnect your node from this cluster. The overall training project will continue on other workers.',
        confirmText: 'Stop Contribution',
        isDestructive: true,
        action: () => {
          updateWorkerControls('stop');
          closeDialog();
          navigate('/');
        }
      });
    };

    return (
      <div className="page-container wide">
        {/* Header */}
        <div className="progress-header">
          <div className="project-meta">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '22px' }}>{workerProject.projectName}</h1>
              <span
                className={`badge ${
                  isGloballyPaused
                    ? 'badge-paused'
                    : isPaused
                    ? 'badge-paused'
                    : 'badge-active'
                }`}
              >
                {isGloballyPaused
                  ? 'Globally Paused'
                  : isPaused
                  ? 'Contribution Paused'
                  : 'Computing Gradients'}
              </span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Assigned Task: <strong>{workerProject.assignedTask}</strong>
            </p>
          </div>

          <ProjectCode
            code={workerProject.projectCode}
            label="Joined Project Code"
            showCopy={false}
          />
        </div>

        {/* Overall Project Progress Readout */}
        <div style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span className="metric-label">Cluster Training Progress</span>
            <span style={{ fontSize: '14px', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
              {workerProject.currentProgress.toFixed(1)}%
            </span>
          </div>
          <div className="progress-bar-container">
            <div
              className="progress-bar-fill"
              style={{ width: `${workerProject.currentProgress}%` }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
            <span>Step {workerProject.currentStep.toLocaleString()} of {workerProject.totalSteps.toLocaleString()}</span>
            <span>Cluster Status: Active</span>
          </div>
        </div>

        {/* Live Resource Telemetry Cards */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '12px' }}>
            Live Node Telemetry & Allocated Contribution
          </h3>

          <div className="metrics-grid">
            <div className="metric-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <Cpu size={14} />
                <span className="metric-label">CPU Usage</span>
              </div>
              <span className="metric-value">
                {isPaused ? '0%' : `${workerProject.cpuUsage}%`}
              </span>
              <small style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                Allocated: {workerProject.allocation.allocatedCpuCores} Cores ({workerProject.allocation.cpuPercent}%)
              </small>
            </div>

            <div className="metric-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <Server size={14} />
                <span className="metric-label">RAM Allocated & Used</span>
              </div>
              <span className="metric-value">
                {isPaused ? '1.2 GB' : `${workerProject.ramUsageGb} GB`}
              </span>
              <small style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                Budget: {workerProject.allocation.ramGb} GB
              </small>
            </div>

            <div className="metric-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <Activity size={14} />
                <span className="metric-label">GPU Load</span>
              </div>
              <span className="metric-value">
                {isPaused ? '0%' : `${workerProject.gpuUsage}%`}
              </span>
              <small style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                Contribution Limit: {workerProject.allocation.gpuPercent}% (~{workerProject.allocation.allocatedVramGb} GB VRAM)
              </small>
            </div>

            <div className="metric-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                <Layers size={14} />
                <span className="metric-label">Storage Cache</span>
              </div>
              <span className="metric-value">
                {Math.round(workerProject.allocation.storageGb * 0.42)} GB
              </span>
              <small style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                Max Cache: {workerProject.allocation.storageGb} GB
              </small>
            </div>
          </div>
        </div>

        {/* Worker Controls */}
        <div className="controls-bar">
          <span style={{ fontSize: '13px', fontWeight: 600, marginRight: '6px' }}>
            Worker Controls:
          </span>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleWorkerPauseResume}
            disabled={isGloballyPaused}
          >
            {isPaused ? (
              <>
                <Play size={15} fill="currentColor" />
                <span>Resume Contribution</span>
              </>
            ) : (
              <>
                <Pause size={15} />
                <span>Pause Contribution</span>
              </>
            )}
          </button>

          <button
            type="button"
            className="btn btn-danger"
            onClick={handleWorkerStop}
          >
            <Square size={15} />
            <span>Stop My Contribution</span>
          </button>
        </div>

        {/* Worker Info Callout */}
        <div
          style={{
            marginTop: '24px',
            padding: '14px 18px',
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}
        >
          <CheckCircle size={18} color="#10a37f" />
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Your worker node is securely synchronizing model gradients with the cluster via ADC peer-to-peer transport.
          </div>
        </div>

        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          title={confirmDialog.title}
          message={confirmDialog.message}
          confirmText={confirmDialog.confirmText}
          isDestructive={confirmDialog.isDestructive}
          onConfirm={confirmDialog.action}
          onCancel={closeDialog}
        />
      </div>
    );
  }

  // Fallback if no role connected
  return (
    <div className="page-container centered">
      <h2 style={{ marginBottom: '8px' }}>No Agent Connected</h2>
      <p style={{ marginBottom: '20px', color: 'var(--text-secondary)' }}>
        Please select an agent role from the dashboard or demo simulation switcher.
      </p>
      <button type="button" className="btn btn-primary" onClick={() => navigate('/')}>
        Go to Dashboard
      </button>
    </div>
  );
};
