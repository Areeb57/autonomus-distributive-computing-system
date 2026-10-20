import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Play,
  Pause,
  Square,
  Clock,
  Gauge,
  TrendingDown,
  Server,
  Sparkles,
  Shield,
  UserCheck,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Badge } from '../components/common/Badge';
import { ProgressBar } from '../components/progress/ProgressBar';
import { WorkerCard } from '../components/cards/WorkerCard';
import { TrainingCharts } from '../components/charts/TrainingCharts';
import { LiveLogsPanel } from '../components/logs/LiveLogsPanel';
import { Modal } from '../components/common/Modal';

export const ProjectProgressPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const {
    projects,
    activeProjectId,
    getProjectById,
    pauseProjectTraining,
    resumeProjectTraining,
    stopProjectTraining,
    stopProjectAsMaster,
    pauseWorkerContribution,
    resumeWorkerContribution,
    stopWorkerContribution,
  } = useApp();

  // Find project: by URL param or fallback to activeProjectId or first project
  const currentProjectId = projectId || activeProjectId || projects[0]?.id;
  const project = getProjectById(currentProjectId);

  // Modals for confirmations
  const [showStopTrainingModal, setShowStopTrainingModal] = useState(false);
  const [showStopProjectModal, setShowStopProjectModal] = useState(false);
  const [showStopWorkerModal, setShowStopWorkerModal] = useState(false);

  if (!project) {
    return (
      <div className="card" style={{ padding: '60px 20px', textAlign: 'center' }}>
        <h2 style={{ marginBottom: 12 }}>Project Not Found</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
          The requested training project does not exist or has been removed.
        </p>
        <button className="btn btn-primary" onClick={() => navigate('/projects')}>
          Browse Available Projects
        </button>
      </div>
    );
  }

  // Derive current user relationship to THIS specific project
  const isMasterOfThisProject = project.owner.isCurrentUser;
  const userWorkerNode = project.workers.find((w) => w.isCurrentUser);
  const isWorkerOfThisProject = !!userWorkerNode;

  // Compute format for elapsed time and remaining time
  const formatSeconds = (sec: number) => {
    const hours = Math.floor(sec / 3600);
    const minutes = Math.floor((sec % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m ${sec % 60}s`;
  };

  const isPaused = project.status === 'paused';
  const isTraining = project.status === 'training';
  const isStopped = project.status === 'stopped' || project.status === 'completed';

  const userWorkerIsPaused = userWorkerNode?.status === 'paused';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 26 }} className="animate-fade-in">
      {/* SECTION A: Project Header */}
      <div
        className="card card-glow"
        style={{
          padding: '24px 28px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 14 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
              <Badge status={project.status} pulse={isTraining} />
              
              {/* User's Contextual Role Badge */}
              {isMasterOfThisProject && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    padding: '3px 10px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: 'var(--accent-primary-light)',
                    color: 'var(--accent-primary)',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                  }}
                >
                  <Shield size={13} />
                  You: Master Coordinator
                </span>
              )}

              {isWorkerOfThisProject && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    padding: '3px 10px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: 'var(--status-online-bg)',
                    color: 'var(--status-online)',
                    border: '1px solid var(--status-online-border)',
                  }}
                >
                  <UserCheck size={13} />
                  You: Contributing Worker
                </span>
              )}

              {!isMasterOfThisProject && !isWorkerOfThisProject && (
                <span
                  style={{
                    fontSize: '0.78rem',
                    padding: '3px 10px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: 'rgba(255, 255, 255, 0.06)',
                    color: 'var(--text-muted)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  Observing (Non-participant)
                </span>
              )}

              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                ID: {project.id}
              </span>
            </div>

            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 4 }}>
              {project.name}
            </h1>

            <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', maxWidth: 880 }}>
              {project.description}
            </p>
          </div>

          {/* Quick Action Buttons for Non-participants */}
          {!isMasterOfThisProject && !isWorkerOfThisProject && (
            <button
              className="btn btn-primary"
              onClick={() => navigate(`/worker-setup/${project.id}`)}
            >
              <Sparkles size={16} />
              <span>Join as Worker Node</span>
            </button>
          )}
        </div>

        {/* Project Metadata Specs */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 12,
            padding: '12px 16px',
            backgroundColor: 'var(--bg-input)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.82rem',
          }}
        >
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase' }}>
              Project Owner
            </span>
            <strong style={{ color: 'var(--text-primary)' }}>{project.owner.name}</strong>
          </div>

          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase' }}>
              Architecture
            </span>
            <strong style={{ color: 'var(--accent-primary)' }}>{project.modelArchitecture}</strong>
          </div>

          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase' }}>
              Dataset
            </span>
            <strong style={{ color: 'var(--accent-cyan)' }}>
              {project.datasetName} ({project.datasetSize})
            </strong>
          </div>

          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase' }}>
              Training Strategy
            </span>
            <strong style={{ color: 'var(--text-primary)' }}>{project.trainingStrategy}</strong>
          </div>

          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase' }}>
              Nodes Participating
            </span>
            <strong className="mono" style={{ color: 'var(--status-online)' }}>
              {project.workers.length} of {project.workersNeeded} Nodes
            </strong>
          </div>
        </div>

        {/* SECTION E & F: ROLE-SPECIFIC CONTROLS BAR */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 12,
            borderTop: '1px solid var(--border-subtle)',
            paddingTop: 14,
          }}
        >
          {/* Master Controls */}
          {isMasterOfThisProject ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', width: '100%', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Master Project Controls:
                </span>
                {isTraining ? (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => pauseProjectTraining(project.id)}
                    style={{ borderColor: 'var(--status-paused)', color: 'var(--status-paused)' }}
                  >
                    <Pause size={14} />
                    <span>Pause Training</span>
                  </button>
                ) : isPaused ? (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => resumeProjectTraining(project.id)}
                  >
                    <Play size={14} />
                    <span>Resume Training</span>
                  </button>
                ) : null}

                {!isStopped && (
                  <button
                    className="btn btn-danger-outline btn-sm"
                    onClick={() => setShowStopTrainingModal(true)}
                  >
                    <Square size={14} />
                    <span>Stop Training</span>
                  </button>
                )}
              </div>

              <div>
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => setShowStopProjectModal(true)}
                >
                  <span>Stop Project Management</span>
                </button>
              </div>
            </div>
          ) : isWorkerOfThisProject ? (
            /* Worker Controls */
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', width: '100%', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Your Volunteer Worker Controls:
                </span>

                {userWorkerIsPaused ? (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => resumeWorkerContribution(project.id)}
                  >
                    <Play size={14} />
                    <span>Resume Contribution</span>
                  </button>
                ) : (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => pauseWorkerContribution(project.id)}
                    style={{ borderColor: 'var(--status-paused)' }}
                  >
                    <Pause size={14} />
                    <span>Pause Contribution</span>
                  </button>
                )}
              </div>

              <button
                className="btn btn-danger-outline btn-sm"
                onClick={() => setShowStopWorkerModal(true)}
              >
                <span>Stop Contributing & Leave</span>
              </button>
            </div>
          ) : (
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              You are currently viewing this project as an observer. Connect as a volunteer worker to contribute computing power.
            </div>
          )}
        </div>
      </div>

      {/* SECTION B: Overall Training Progress Section */}
      <div className="card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>
              Overall Distributed Training Progress
            </h3>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Step advancement synchronized via simulated Ring-AllReduce consensus
            </span>
          </div>
          <span
            style={{
              fontSize: '0.72rem',
              padding: '2px 8px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              color: 'var(--text-muted)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            Simulated Demo Telemetry
          </span>
        </div>

        {/* Large Progress Bar */}
        <ProgressBar
          percentage={project.metrics.progressPercent}
          status={project.status}
          height={14}
          showLabel
        />

        {/* Metric Cards Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 14,
            marginTop: 20,
          }}
        >
          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase' }}>Current Step</span>
            <strong className="mono" style={{ fontSize: '1.25rem', color: 'var(--accent-primary)' }}>
              {project.metrics.currentStep.toLocaleString()}
            </strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>
              of {project.metrics.totalSteps.toLocaleString()}
            </span>
          </div>

          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <TrendingDown size={14} color="var(--status-online)" />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Loss</span>
            </div>
            <strong className="mono" style={{ fontSize: '1.25rem', color: 'var(--status-online)' }}>
              {project.metrics.currentLoss.toFixed(4)}
            </strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>
              Validation checkpoint
            </span>
          </div>

          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Gauge size={14} color="var(--accent-cyan)" />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Speed</span>
            </div>
            <strong className="mono" style={{ fontSize: '1.25rem', color: 'var(--text-primary)' }}>
              {project.metrics.trainingSpeed}
            </strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>
              steps / second
            </span>
          </div>

          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Clock size={14} color="var(--text-muted)" />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Elapsed Time</span>
            </div>
            <strong className="mono" style={{ fontSize: '1.25rem', color: 'var(--text-primary)' }}>
              {formatSeconds(project.metrics.elapsedTimeSeconds)}
            </strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>
              Active runtime
            </span>
          </div>

          <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block', textTransform: 'uppercase' }}>Estimated Remaining</span>
            <strong className="mono" style={{ fontSize: '1.25rem', color: 'var(--status-paused)' }}>
              ~{formatSeconds(project.metrics.estimatedRemainingSeconds)}
            </strong>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'block' }}>
              Based on cluster speed
            </span>
          </div>
        </div>
      </div>

      {/* SECTION C: Training Charts with Recharts */}
      <TrainingCharts history={project.metrics.history} />

      {/* SECTION D: Participating Worker Node Cards */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
              Participating Compute Nodes ({project.workers.length})
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Individual volunteer machines executing partitioned micro-batches
            </span>
          </div>

          {isWorkerOfThisProject && (
            <span
              style={{
                fontSize: '0.78rem',
                color: 'var(--accent-primary)',
                fontWeight: 600,
                backgroundColor: 'var(--accent-primary-light)',
                padding: '4px 10px',
                borderRadius: 'var(--radius-full)',
              }}
            >
              Your node is connected
            </span>
          )}
        </div>

        {project.workers.length === 0 ? (
          <div className="card" style={{ padding: '40px 20px', textAlign: 'center' }}>
            <Server size={32} color="var(--text-muted)" style={{ margin: '0 auto 12px' }} />
            <h4 style={{ fontSize: '1.05rem', fontWeight: 600 }}>No Workers Connected Yet</h4>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginTop: 4 }}>
              This project is online and waiting for volunteer compute nodes to join the cluster.
            </p>
            {!isWorkerOfThisProject && (
              <button
                className="btn btn-primary btn-sm"
                style={{ marginTop: 16 }}
                onClick={() => navigate(`/worker-setup/${project.id}`)}
              >
                Join as First Worker
              </button>
            )}
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: 18,
            }}
          >
            {project.workers.map((worker) => (
              <WorkerCard
                key={worker.id}
                worker={worker}
                onPause={() => pauseWorkerContribution(project.id)}
                onResume={() => resumeWorkerContribution(project.id)}
                onStop={() => setShowStopWorkerModal(true)}
                showPersonalControls={isWorkerOfThisProject}
              />
            ))}
          </div>
        )}
      </div>

      {/* SECTION G: Live Event and Consensus Logs */}
      <LiveLogsPanel logs={project.logs} />

      {/* CONFIRMATION MODALS */}

      {/* Master: Stop Training Modal */}
      <Modal
        isOpen={showStopTrainingModal}
        onClose={() => setShowStopTrainingModal(false)}
        title="Stop Cluster Training?"
        variant="warning"
        confirmLabel="Stop Training"
        onConfirm={() => {
          stopProjectTraining(project.id);
          setShowStopTrainingModal(false);
        }}
      >
        <p>
          Are you sure you want to stop the simulated training run for <strong>{project.name}</strong>?
        </p>
        <ul style={{ marginTop: 10, paddingLeft: 20, fontSize: '0.88rem', lineHeight: 1.6 }}>
          <li>Halts step advancement across all connected worker machines.</li>
          <li>Saves current model checkpoint to the simulated storage pool.</li>
          <li>Status will change to <strong>Stopped</strong> for all participants.</li>
        </ul>
      </Modal>

      {/* Master: Stop Project Modal */}
      <Modal
        isOpen={showStopProjectModal}
        onClose={() => setShowStopProjectModal(false)}
        title="Stop Project Management?"
        variant="danger"
        confirmLabel="End Master Role & Close"
        onConfirm={() => {
          stopProjectAsMaster(project.id);
          setShowStopProjectModal(false);
          navigate('/');
        }}
      >
        <p>
          This action ends your role as Master for <strong>{project.name}</strong>.
        </p>
        <p style={{ marginTop: 8, fontSize: '0.88rem' }}>
          Unlike pausing training, ending project management unregisters the coordinator and
          returns you to the Dashboard as a non-participant.
        </p>
      </Modal>

      {/* Worker: Stop Contributing Modal */}
      <Modal
        isOpen={showStopWorkerModal}
        onClose={() => setShowStopWorkerModal(false)}
        title="Withdraw from Compute Cluster?"
        variant="danger"
        confirmLabel="Stop Contributing & Exit"
        onConfirm={() => {
          stopWorkerContribution(project.id);
          setShowStopWorkerModal(false);
          navigate('/');
        }}
      >
        <p>
          Are you sure you want to disconnect your volunteer node from <strong>{project.name}</strong>?
        </p>
        <ul style={{ marginTop: 10, paddingLeft: 20, fontSize: '0.88rem', lineHeight: 1.6 }}>
          <li>Removes your computer from the participating worker list.</li>
          <li>Restores your local hardware capacity.</li>
          <li>The project continues training with other volunteer nodes.</li>
        </ul>
      </Modal>
    </div>
  );
};
