import type { ConnectedWorker } from '../types';
import { Cpu, Server, Activity } from 'lucide-react';

interface WorkerCardProps {
  worker: ConnectedWorker;
}

export const WorkerCard: React.FC<WorkerCardProps> = ({ worker }) => {
  const getBadgeClass = (status: ConnectedWorker['status']) => {
    switch (status) {
      case 'computing':
      case 'active':
        return 'badge-active';
      case 'paused':
        return 'badge-paused';
      case 'idle':
      default:
        return 'badge-neutral';
    }
  };

  return (
    <div className="worker-card">
      <div className="worker-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Server size={16} color="var(--text-secondary)" />
          <span className="worker-name">{worker.name}</span>
        </div>
        <span className={`badge ${getBadgeClass(worker.status)}`}>
          <span
            className="status-dot active"
            style={{
              backgroundColor:
                worker.status === 'computing' || worker.status === 'active'
                  ? '#10a37f'
                  : '#f59e0b'
            }}
          />
          {worker.status.charAt(0).toUpperCase() + worker.status.slice(1)}
        </span>
      </div>

      <div className="worker-meta-row">
        <div className="worker-meta-item">
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
            <Cpu size={12} />
            <span>CPU</span>
          </div>
          <strong>
            {worker.allocatedCpuCores} / {worker.cpuCores} Cores
          </strong>
        </div>

        <div className="worker-meta-item">
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
            <Server size={12} />
            <span>RAM</span>
          </div>
          <strong>
            {worker.allocatedRamGb} / {worker.ramGb} GB
          </strong>
        </div>

        <div className="worker-meta-item" style={{ gridColumn: 'span 2' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
            <Activity size={12} />
            <span>GPU Allocation</span>
          </div>
          <strong>
            {worker.gpuName} ({worker.allocatedGpuPercent}% power)
          </strong>
        </div>
      </div>

      <div
        style={{
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '8px',
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '11px',
          color: 'var(--text-muted)'
        }}
      >
        <span>{worker.currentBatch}</span>
        <span>{worker.latencyMs}ms ping</span>
      </div>
    </div>
  );
};
