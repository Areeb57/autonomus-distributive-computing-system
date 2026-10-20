import React from 'react';
import type { Project } from '../../types';
import { Layers, Database, Users, Cpu, ArrowRight, UserCheck } from 'lucide-react';
import { Badge } from '../common/Badge';
import { ProgressBar } from '../progress/ProgressBar';

interface ProjectCardProps {
  project: Project;
  onView: (id: string) => void;
  onJoin?: (id: string) => void;
  isUserMember?: boolean;
  isUserMaster?: boolean;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({
  project,
  onView,
  onJoin,
  isUserMember = false,
  isUserMaster = false,
}) => {
  const isAvailableToJoin =
    project.status === 'online' ||
    project.status === 'looking_for_workers' ||
    (project.status === 'training' && project.workers.length < project.workersNeeded);

  const activeWorkersCount = project.workers.filter(
    (w) => w.status === 'training' && w.contributionStatus === 'active'
  ).length;

  return (
    <div
      className="card card-interactive"
      onClick={() => onView(project.id)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: 16,
      }}
    >
      <div>
        {/* Top Badges & Status */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 10,
            marginBottom: 10,
          }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <Badge status={project.status} pulse={project.status === 'training'} />
            {isUserMaster && (
              <span
                style={{
                  fontSize: '0.72rem',
                  padding: '3px 8px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--accent-primary-light)',
                  color: 'var(--accent-primary)',
                  fontWeight: 600,
                }}
              >
                Owner
              </span>
            )}
            {isUserMember && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: '0.72rem',
                  padding: '3px 8px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--status-online-bg)',
                  color: 'var(--status-online)',
                  fontWeight: 600,
                }}
              >
                <UserCheck size={12} />
                Joined
              </span>
            )}
          </div>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            by {project.owner.name}
          </span>
        </div>

        {/* Title & Description */}
        <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: 8 }}>
          {project.name}
        </h3>
        <p
          style={{
            fontSize: '0.85rem',
            color: 'var(--text-secondary)',
            lineHeight: 1.5,
            marginBottom: 16,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {project.description}
        </p>

        {/* Spec Tags */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 8,
            marginBottom: 16,
            fontSize: '0.8rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              color: 'var(--text-secondary)',
              backgroundColor: 'var(--bg-input)',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <Layers size={14} color="var(--accent-primary)" />
            <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
              {project.modelArchitecture}
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              color: 'var(--text-secondary)',
              backgroundColor: 'var(--bg-input)',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <Database size={14} color="var(--accent-cyan)" />
            <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
              {project.datasetName} ({project.datasetSize})
            </span>
          </div>
        </div>

        {/* Workers & Requirements Summary */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
            marginBottom: 12,
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Users size={14} />
            <strong style={{ color: 'var(--text-primary)' }}>{project.workers.length}</strong> / {project.workersNeeded} Nodes ({activeWorkersCount} active)
          </span>

          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Cpu size={14} />
            Req: {project.requirements.minCpuCores}C / {project.requirements.minRamGB}GB
            {project.requirements.gpuRecommended ? ' + GPU' : ''}
          </span>
        </div>

        {/* Progress Bar */}
        <div>
          <ProgressBar
            percentage={project.metrics.progressPercent}
            status={project.status}
            showLabel
          />
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.74rem',
              color: 'var(--text-muted)',
              marginTop: 4,
            }}
          >
            <span>Step {project.metrics.currentStep.toLocaleString()} / {project.metrics.totalSteps.toLocaleString()}</span>
            <span>Loss: {project.metrics.currentLoss.toFixed(3)}</span>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div
        style={{
          display: 'flex',
          gap: 10,
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: 14,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => onView(project.id)}
          style={{ flex: 1 }}
        >
          View Project
        </button>

        {isAvailableToJoin && !isUserMember && onJoin && (
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onJoin(project.id)}
            style={{ flex: 1.2 }}
          >
            <span>Join as Worker</span>
            <ArrowRight size={14} />
          </button>
        )}

        {isUserMember && (
          <button
            className="btn btn-outline btn-sm"
            onClick={() => onView(project.id)}
            style={{ flex: 1.2, borderColor: 'var(--status-online)', color: 'var(--status-online)' }}
          >
            Contributed Node
          </button>
        )}
      </div>
    </div>
  );
};
