import React from 'react';
import type { WorkerNode } from '../../types';
import { Cpu, HardDrive, Zap, Clock, Activity, UserCheck } from 'lucide-react';
import { Badge } from '../common/Badge';

interface WorkerCardProps {
  worker: WorkerNode;
  onPause?: () => void;
  onResume?: () => void;
  onStop?: () => void;
  showPersonalControls?: boolean;
}

export const WorkerCard: React.FC<WorkerCardProps> = ({
  worker,
  onPause,
  onResume,
  onStop,
  showPersonalControls = false,
}) => {
  const isPaused = worker.status === 'paused' || worker.contributionStatus === 'paused';
  const isTraining = worker.status === 'training' && worker.contributionStatus === 'active';

  const cpuPercent = Math.round((worker.cpuCoresContributed / Math.max(1, worker.cpuCoresTotal)) * 100);
  const ramPercent = Math.round((worker.ramContributedGB / Math.max(1, worker.ramTotalGB)) * 100);

  return (
    <div
      className={`card ${worker.isCurrentUser ? 'card-glow' : ''}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        padding: '18px 20px',
        borderColor: worker.isCurrentUser ? 'var(--accent-primary)' : 'var(--border-subtle)',
        backgroundColor: worker.isCurrentUser ? 'rgba(99, 102, 241, 0.04)' : 'var(--bg-card)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              backgroundColor: isTraining
                ? 'var(--status-online-bg)'
                : isPaused
                ? 'var(--status-paused-bg)'
                : 'var(--bg-card-elevated)',
              color: isTraining
                ? 'var(--status-online)'
                : isPaused
                ? 'var(--status-paused)'
                : 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Activity size={18} className={isTraining ? 'animate-pulse' : ''} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
                {worker.name}
              </span>
              {worker.isCurrentUser && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: '0.72rem',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: 'var(--accent-primary-light)',
                    color: 'var(--accent-primary)',
                    fontWeight: 600,
                  }}
                >
                  <UserCheck size={12} />
                  Your Node
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
              <Clock size={12} color="var(--text-muted)" />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Heartbeat: {worker.lastHeartbeat}
              </span>
            </div>
          </div>
        </div>

        <Badge status={worker.status} pulse={isTraining}>
          {isTraining ? 'Training Active' : isPaused ? 'Paused' : 'Idle'}
        </Badge>
      </div>

      {/* Hardware breakdown meters */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.85rem' }}>
        {/* CPU */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
              <Cpu size={14} color="var(--text-muted)" />
              CPU Contributed
            </span>
            <span className="mono" style={{ fontWeight: 600 }}>
              {worker.cpuCoresContributed} / {worker.cpuCoresTotal} Cores ({cpuPercent}%)
            </span>
          </div>
          <div className="progress-bar-container" style={{ height: 6 }}>
            <div
              className={`progress-bar-fill ${isPaused ? 'status-paused' : ''}`}
              style={{ width: `${cpuPercent}%` }}
            />
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>
            {worker.cpuModel}
          </div>
        </div>

        {/* RAM */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
              <HardDrive size={14} color="var(--text-muted)" />
              RAM Budget
            </span>
            <span className="mono" style={{ fontWeight: 600 }}>
              {worker.ramContributedGB} / {worker.ramTotalGB} GB ({ramPercent}%)
            </span>
          </div>
          <div className="progress-bar-container" style={{ height: 6 }}>
            <div
              className={`progress-bar-fill ${isPaused ? 'status-paused' : ''}`}
              style={{ width: `${ramPercent}%` }}
            />
          </div>
        </div>

        {/* GPU */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
              <Zap size={14} color={worker.gpuEnabled ? 'var(--status-online)' : 'var(--text-muted)'} />
              GPU Acceleration
            </span>
            <span
              className="mono"
              style={{
                fontWeight: 600,
                color: worker.gpuEnabled ? 'var(--status-online)' : 'var(--text-muted)',
              }}
            >
              {worker.gpuEnabled ? 'Enabled' : 'CPU Only'}
            </span>
          </div>
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              backgroundColor: 'var(--bg-input)',
              padding: '4px 8px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              marginTop: 4,
            }}
          >
            {worker.gpuModel} {worker.gpuMemoryTotalGB > 0 ? `(${worker.gpuMemoryTotalGB} GB VRAM)` : ''}
          </div>
        </div>
      </div>

      {/* Workload Stats */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 8,
          padding: '10px 12px',
          backgroundColor: 'var(--bg-input)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          fontSize: '0.78rem',
        }}
      >
        <div>
          <span style={{ color: 'var(--text-muted)', display: 'block' }}>Batch Size</span>
          <span className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {worker.currentBatch} samples
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', display: 'block' }}>Steps Processed</span>
          <span className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {worker.stepsProcessed.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Personal Controls (when user is worker viewing their card) */}
      {showPersonalControls && worker.isCurrentUser && (
        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          {isPaused ? (
            <button
              className="btn btn-secondary btn-sm"
              onClick={onResume}
              style={{ flex: 1, borderColor: 'var(--status-online)' }}
            >
              Resume Node
            </button>
          ) : (
            <button
              className="btn btn-secondary btn-sm"
              onClick={onPause}
              style={{ flex: 1, borderColor: 'var(--status-paused)' }}
            >
              Pause Node
            </button>
          )}
          <button
            className="btn btn-danger-outline btn-sm"
            onClick={onStop}
            style={{ flex: 1 }}
          >
            Withdraw Node
          </button>
        </div>
      )}
    </div>
  );
};
