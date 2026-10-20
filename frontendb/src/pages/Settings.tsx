import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { RotateCcw, Moon, Sun } from 'lucide-react';

export const Settings: React.FC = () => {
  const navigate = useNavigate();
  const { userSettings, updateUserSettings, toggleTheme, resetDemo } = useApp();

  const [username, setUsername] = useState(userSettings.username);
  const [email, setEmail] = useState(userSettings.email);
  const [isSaved, setIsSaved] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    updateUserSettings({ username, email });
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  const handleConfirmReset = () => {
    resetDemo();
    setShowResetConfirm(false);
    navigate('/');
  };

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 600 }}>Settings</h1>
      </div>

      {/* Account / Demo Identity */}
      <div className="settings-section">
        <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Demo Account Profile</h2>
        <form onSubmit={handleSaveProfile} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="form-group">
            <label className="form-label" htmlFor="settings-username">
              Username
            </label>
            <input
              type="text"
              id="settings-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="settings-email">
              Email Address
            </label>
            <input
              type="email"
              id="settings-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button type="submit" className="btn btn-secondary btn-sm">
              Save Profile
            </button>
            {isSaved && (
              <span style={{ fontSize: '13px', color: '#10a37f' }}>Saved successfully</span>
            )}
          </div>
        </form>
      </div>

      {/* Appearance / Theme */}
      <div className="settings-section">
        <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Appearance</h2>
        <div className="settings-row">
          <div className="settings-info">
            <span className="settings-label">Color Theme</span>
            <span className="settings-desc">
              Currently using {userSettings.theme === 'dark' ? 'Dark' : 'Light'} theme
            </span>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={toggleTheme}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {userSettings.theme === 'dark' ? (
              <>
                <Sun size={15} />
                <span>Light Theme</span>
              </>
            ) : (
              <>
                <Moon size={15} />
                <span>Dark Theme</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="settings-section">
        <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Notification Preferences</h2>

        <div className="settings-row">
          <div className="settings-info">
            <span className="settings-label">Training Milestones</span>
            <span className="settings-desc">Notify when a training job reaches 25%, 50%, 75%, and 100%</span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={userSettings.notifyMilestones}
              onChange={(e) => updateUserSettings({ notifyMilestones: e.target.checked })}
            />
            <span className="slider-switch" />
          </label>
        </div>

        <div className="settings-row">
          <div className="settings-info">
            <span className="settings-label">Worker Node Disconnects</span>
            <span className="settings-desc">Alert when a worker experiences heartbeat timeout or drops</span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={userSettings.notifyWorkerDisconnect}
              onChange={(e) => updateUserSettings({ notifyWorkerDisconnect: e.target.checked })}
            />
            <span className="slider-switch" />
          </label>
        </div>

        <div className="settings-row">
          <div className="settings-info">
            <span className="settings-label">Thermal Warnings</span>
            <span className="settings-desc">Notify if node temperature triggers compute throttling</span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={userSettings.notifyThermalThrottle}
              onChange={(e) => updateUserSettings({ notifyThermalThrottle: e.target.checked })}
            />
            <span className="slider-switch" />
          </label>
        </div>
      </div>

      {/* Resource Preferences */}
      <div className="settings-section">
        <h2 style={{ fontSize: '15px', fontWeight: 600 }}>Resource Preferences</h2>

        <div className="settings-row">
          <div className="settings-info">
            <span className="settings-label">Battery Saver Auto-Throttle</span>
            <span className="settings-desc">Automatically pause contributions when device battery falls below 20%</span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={userSettings.autoThrottleBattery}
              onChange={(e) => updateUserSettings({ autoThrottleBattery: e.target.checked })}
            />
            <span className="slider-switch" />
          </label>
        </div>

        <div className="settings-row">
          <div className="settings-info">
            <span className="settings-label">Background Training When Idle</span>
            <span className="settings-desc">Allow computing gradient batches in background when system is idle</span>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={userSettings.allowBackgroundTraining}
              onChange={(e) => updateUserSettings({ allowBackgroundTraining: e.target.checked })}
            />
            <span className="slider-switch" />
          </label>
        </div>
      </div>

      {/* Reset Demo Section */}
      <div className="settings-section">
        <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--btn-danger-text)' }}>
          Reset Demo Environment
        </h2>
        <div className="settings-row">
          <div className="settings-info">
            <span className="settings-label">Clear All LocalStorage State</span>
            <span className="settings-desc">
              Resets agent connection, clears current Master/Worker projects, and returns to initial startup view.
            </span>
          </div>

          <button
            type="button"
            className="btn btn-danger btn-sm"
            onClick={() => setShowResetConfirm(true)}
          >
            <RotateCcw size={14} />
            <span>Reset Demo</span>
          </button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={showResetConfirm}
        title="Reset Demo State?"
        message="This will wipe all simulated projects, worker connections, and role settings from localStorage and return you to the initial ADC onboarding screen."
        confirmText="Reset Demo"
        isDestructive={true}
        onConfirm={handleConfirmReset}
        onCancel={() => setShowResetConfirm(false)}
      />
    </div>
  );
};
