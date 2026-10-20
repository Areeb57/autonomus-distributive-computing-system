import React from 'react';
import { Menu, Sun, Moon } from 'lucide-react';
import { useApp } from '../context/AppContext';

interface HeaderProps {
  onToggleSidebar: () => void;
  title: string;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar, title }) => {
  const { userSettings, toggleTheme, role, simulateRoleConnection, backendOnline, refreshBackend } = useApp();

  return (
    <>
      <header className="top-header">
        <div className="header-left">
          <button
            type="button"
            className="btn-icon"
            onClick={onToggleSidebar}
            aria-label="Toggle navigation sidebar"
          >
            <Menu size={18} />
          </button>
          <span className="header-title">{title}</span>
        </div>

        <div className="header-actions" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={() => refreshBackend()}
            title={
              backendOnline
                ? 'FastAPI Backend Online & Synced (port 8000)'
                : 'FastAPI Backend Disconnected — Click to retry connection'
            }
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '9999px',
              fontSize: '12px',
              fontWeight: 500,
              backgroundColor: backendOnline ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)',
              color: backendOnline ? '#059669' : '#d97706',
              border: `1px solid ${backendOnline ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`,
              cursor: 'pointer'
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: backendOnline ? '#10b981' : '#f59e0b'
              }}
            />
            <span>{backendOnline ? 'Backend Connected' : 'Local Mode'}</span>
          </button>

          <button
            type="button"
            className="btn-icon"
            onClick={toggleTheme}
            title={userSettings.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle color theme"
          >
            {userSettings.theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      {/* Demo status banner */}
      <div className="demo-bar">
        <div className="demo-bar-left">
          <span className="demo-badge">Node Role</span>
          <span>
            {role === 'none' && 'Agent: Not Connected'}
            {role === 'master' && 'Agent: Master Node Active'}
            {role === 'worker' && 'Agent: Worker Node Active'}
          </span>
        </div>

        <div className="demo-bar-right">
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Quick Switch:</span>
          <button
            type="button"
            className={`role-chip ${role === 'none' ? 'selected' : ''}`}
            onClick={() => simulateRoleConnection('none')}
          >
            No Agent
          </button>
          <button
            type="button"
            className={`role-chip ${role === 'master' ? 'selected' : ''}`}
            onClick={() => simulateRoleConnection('master')}
          >
            Master
          </button>
          <button
            type="button"
            className={`role-chip ${role === 'worker' ? 'selected' : ''}`}
            onClick={() => simulateRoleConnection('worker')}
          >
            Worker
          </button>
        </div>
      </div>
    </>
  );
};
