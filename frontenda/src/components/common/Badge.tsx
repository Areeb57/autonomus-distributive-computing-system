import React from 'react';
import type { ProjectStatus, WorkerStatus, UserRole } from '../../types';

interface BadgeProps {
  children?: React.ReactNode;
  variant?: 'online' | 'paused' | 'stopped' | 'info' | 'role' | 'neutral';
  status?: ProjectStatus | WorkerStatus;
  role?: UserRole;
  pulse?: boolean;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant,
  status,
  role,
  pulse = false,
  className = '',
}) => {
  // Determine variant based on status or role if not directly provided
  let effectiveVariant = variant || 'neutral';
  let label = children;

  if (status) {
    if (status === 'online' || status === 'training') {
      effectiveVariant = 'online';
      label = label || (status === 'training' ? 'Training Active' : 'Online');
    } else if (status === 'paused' || status === 'looking_for_workers') {
      effectiveVariant = 'paused';
      label = label || (status === 'looking_for_workers' ? 'Seeking Workers' : 'Paused');
    } else if (status === 'stopped' || status === 'offline') {
      effectiveVariant = 'stopped';
      label = label || (status === 'offline' ? 'Offline' : 'Stopped');
    } else if (status === 'completed') {
      effectiveVariant = 'online';
      label = label || 'Completed';
    } else if (status === 'idle') {
      effectiveVariant = 'info';
      label = label || 'Idle';
    }
  }

  if (role) {
    effectiveVariant = 'role';
    if (!label) {
      if (role === 'master') label = 'Master';
      else if (role === 'worker') label = 'Worker';
      else if (role === 'master_and_worker') label = 'Master & Worker';
      else label = 'Not participating';
    }
  }

  return (
    <span className={`badge badge-${effectiveVariant} ${className}`}>
      {pulse && (
        <span
          className="pulse-dot"
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            backgroundColor:
              effectiveVariant === 'online'
                ? 'var(--status-online)'
                : effectiveVariant === 'paused'
                ? 'var(--status-paused)'
                : effectiveVariant === 'stopped'
                ? 'var(--status-stopped)'
                : 'var(--accent-primary)',
          }}
        />
      )}
      {label}
    </span>
  );
};
