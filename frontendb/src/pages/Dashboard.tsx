import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { StepGuide } from '../components/StepGuide';
import { FolderGit2, Sliders } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const { role, masterProject, workerProject } = useApp();
  const navigate = useNavigate();

  // If no agent connected, show initial startup dashboard with 4 steps
  if (role === 'none') {
    return (
      <div className="page-container centered">
        <StepGuide />
      </div>
    );
  }

  // Master Dashboard
  if (role === 'master') {
    const handleMyProject = () => {
      if (masterProject && masterProject.status !== 'ended') {
        navigate('/master/progress');
      } else {
        navigate('/master/setup');
      }
    };

    return (
      <div className="page-container centered">
        <div className="returning-dashboard">
          <h1 className="role-greeting">You are a Master</h1>
          <div className="returning-actions">
            <button
              type="button"
              className="btn btn-primary btn-lg btn-block"
              onClick={handleMyProject}
            >
              <FolderGit2 size={18} />
              <span>My Project</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-lg btn-block"
              onClick={() => navigate('/resources')}
            >
              <Sliders size={18} />
              <span>Resource Settings</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Worker Dashboard
  const handleWorkerProject = () => {
    if (workerProject && workerProject.status !== 'stopped') {
      navigate('/worker/progress');
    } else {
      navigate('/worker/join');
    }
  };

  return (
    <div className="page-container centered">
      <div className="returning-dashboard">
        <h1 className="role-greeting">You are a Worker</h1>
        <div className="returning-actions">
          <button
            type="button"
            className="btn btn-primary btn-lg btn-block"
            onClick={handleWorkerProject}
          >
            <FolderGit2 size={18} />
            <span>My Project</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-lg btn-block"
            onClick={() => navigate('/resources')}
          >
            <Sliders size={18} />
            <span>Resource Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
};
