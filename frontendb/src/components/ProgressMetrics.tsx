import React from 'react';
import { formatDuration } from '../utils/formatting';

interface ProgressMetricsProps {
  progress: number;
  currentStep: number;
  totalSteps: number;
  loss?: number;
  speed?: string;
  elapsedSeconds: number;
  estimatedRemainingSeconds?: number;
}

export const ProgressMetrics: React.FC<ProgressMetricsProps> = ({
  progress,
  currentStep,
  totalSteps,
  loss,
  speed,
  elapsedSeconds,
  estimatedRemainingSeconds
}) => {
  return (
    <div>
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span className="metric-label">Overall Progress</span>
          <span style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
            {progress.toFixed(1)}%
          </span>
        </div>
        <div className="progress-bar-container">
          <div
            className="progress-bar-fill"
            style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)' }}>
          <span>Step {currentStep.toLocaleString()} of {totalSteps.toLocaleString()}</span>
          <span>{progress >= 100 ? 'Completed' : 'Training active'}</span>
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-label">Current Step</span>
          <span className="metric-value">
            {currentStep.toLocaleString()}
            <small style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '4px' }}>
              /{totalSteps.toLocaleString()}
            </small>
          </span>
        </div>

        {loss !== undefined && (
          <div className="metric-card">
            <span className="metric-label">Training Loss</span>
            <span className="metric-value">{loss.toFixed(4)}</span>
          </div>
        )}

        {speed && (
          <div className="metric-card">
            <span className="metric-label">Training Speed</span>
            <span className="metric-value" style={{ fontSize: '17px' }}>{speed}</span>
          </div>
        )}

        <div className="metric-card">
          <span className="metric-label">Elapsed Time</span>
          <span className="metric-value" style={{ fontSize: '17px' }}>
            {formatDuration(elapsedSeconds)}
          </span>
        </div>

        {estimatedRemainingSeconds !== undefined && (
          <div className="metric-card">
            <span className="metric-label">Estimated Remaining</span>
            <span className="metric-value" style={{ fontSize: '17px' }}>
              {formatDuration(estimatedRemainingSeconds)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
