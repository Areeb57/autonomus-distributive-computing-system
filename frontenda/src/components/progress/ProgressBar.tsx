import React from 'react';
import type { ProjectStatus } from '../../types';

interface ProgressBarProps {
  percentage: number;
  status?: ProjectStatus;
  height?: number;
  showLabel?: boolean;
  animate?: boolean;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  percentage,
  status = 'training',
  height = 10,
  showLabel = false,
  animate = true,
  className = '',
}) => {
  const clamped = Math.min(100, Math.max(0, percentage));

  let fillClass = '';
  if (status === 'paused' || status === 'looking_for_workers') {
    fillClass = 'status-paused';
  } else if (status === 'stopped') {
    fillClass = 'status-stopped';
  }

  return (
    <div style={{ width: '100%' }} className={className}>
      {showLabel && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 6,
            fontSize: '0.85rem',
          }}
        >
          <span style={{ color: 'var(--text-secondary)' }}>Training Progress</span>
          <span className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {clamped}%
          </span>
        </div>
      )}
      <div className="progress-bar-container" style={{ height }}>
        <div
          className={`progress-bar-fill ${fillClass}`}
          style={{
            width: `${clamped}%`,
            transition: animate ? 'width 0.4s ease-out' : 'none',
          }}
        />
      </div>
    </div>
  );
};
