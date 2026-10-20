import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderGit2,
  Sliders,
  Settings as SettingsIcon,
  X,
  Cpu
} from 'lucide-react';
import { useApp } from '../context/AppContext';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { role, masterProject, workerProject } = useApp();
  const navigate = useNavigate();

  // Smart routing for "My Project" based on role & active project
  const handleMyProjectClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (role === 'none') {
      return; // Disabled
    }
    if (role === 'master') {
      if (masterProject && masterProject.status !== 'ended') {
        navigate('/master/progress');
      } else {
        navigate('/master/setup');
      }
    } else if (role === 'worker') {
      if (workerProject && workerProject.status !== 'stopped') {
        navigate('/worker/progress');
      } else {
        navigate('/worker/join');
      }
    }
    onClose();
  };

  const isMyProjectActive = () => {
    const path = window.location.pathname;
    return path.startsWith('/master/') || path.startsWith('/worker/');
  };

  return (
    <>
      {/* Mobile overlay backdrop */}
      <div
        className={`sidebar-backdrop ${isOpen ? 'active' : ''}`}
        onClick={onClose}
      />

      <aside className={`sidebar ${isOpen ? '' : 'collapsed'}`}>
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">
              <Cpu size={16} />
            </div>
            <span>ADC</span>
          </div>

          <button
            type="button"
            className="btn-icon"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="sidebar-nav">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            onClick={onClose}
          >
            <LayoutDashboard size={17} />
            <span>Dashboard</span>
          </NavLink>

          <a
            href="#my-project"
            onClick={handleMyProjectClick}
            className={`sidebar-link ${isMyProjectActive() ? 'active' : ''} ${
              role === 'none' ? 'disabled' : ''
            }`}
            title={role === 'none' ? 'Connect an agent to access projects' : 'View project'}
          >
            <FolderGit2 size={17} />
            <span>My Project</span>
          </a>

          <NavLink
            to="/resources"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            onClick={onClose}
          >
            <Sliders size={17} />
            <span>Resource Settings</span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            onClick={onClose}
          >
            <SettingsIcon size={17} />
            <span>Settings</span>
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="agent-status-pill">
            <span
              className={`status-dot ${role === 'none' ? 'disconnected' : 'active'}`}
            />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontWeight: 600, fontSize: '11px', color: 'var(--text-primary)' }}>
                {role === 'none' && 'No Agent Connected'}
                {role === 'master' && 'Master Node'}
                {role === 'worker' && 'Worker Node'}
              </span>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                {role === 'none' ? 'Simulated Offline' : 'Demo Handshake Active'}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
