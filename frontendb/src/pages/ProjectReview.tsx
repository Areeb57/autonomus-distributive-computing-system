import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { ArrowLeft, Play } from 'lucide-react';

export const ProjectReview: React.FC = () => {
  const navigate = useNavigate();
  const { pendingMasterDraft, masterProject, putMasterProjectOnline } = useApp();

  const data = pendingMasterDraft || (masterProject ? {
    name: masterProject.name,
    description: masterProject.description,
    datasetFileName: masterProject.datasetFileName,
    datasetFileSize: masterProject.datasetFileSize,
    codeFileName: masterProject.codeFileName,
    codeFileSize: masterProject.codeFileSize
  } : null);

  if (!data || !data.name || !data.datasetFileName || !data.codeFileName) {
    return (
      <div className="page-container centered">
        <p style={{ marginBottom: '16px' }}>No pending project details to review.</p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate('/master/setup')}
        >
          Go to Project Setup
        </button>
      </div>
    );
  }

  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handlePutOnline = async () => {
    setIsSubmitting(true);
    try {
      await putMasterProjectOnline();
      navigate('/master/progress');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 600 }}>Review Project</h1>
      </div>

      <div className="review-summary-list" style={{ marginBottom: '24px' }}>
        <div className="review-item">
          <span className="review-label">Project Name</span>
          <span className="review-value">{data.name}</span>
        </div>

        <div className="review-item">
          <span className="review-label">Description</span>
          <span className="review-value">
            {data.description || <span style={{ color: 'var(--text-muted)' }}>None provided</span>}
          </span>
        </div>

        <div className="review-item">
          <span className="review-label">Dataset File</span>
          <span className="review-value">
            {data.datasetFileName}{' '}
            {data.datasetFileSize && (
              <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                ({data.datasetFileSize})
              </span>
            )}
          </span>
        </div>

        <div className="review-item">
          <span className="review-label">Training Code</span>
          <span className="review-value">
            {data.codeFileName}{' '}
            {data.codeFileSize && (
              <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                ({data.codeFileSize})
              </span>
            )}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate('/master/setup')}
        >
          <ArrowLeft size={16} />
          <span>Back to Editing</span>
        </button>

        <button
          type="button"
          className="btn btn-primary"
          onClick={handlePutOnline}
          disabled={isSubmitting}
        >
          <Play size={16} fill="currentColor" />
          <span>{isSubmitting ? 'Putting Online...' : 'Put Project Online'}</span>
        </button>
      </div>
    </div>
  );
};
