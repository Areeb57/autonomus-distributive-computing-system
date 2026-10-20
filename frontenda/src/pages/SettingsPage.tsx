import React, { useState } from 'react';
import {
  User,
  Palette,
  Bell,
  Sliders,
  RotateCcw,
  Save,
  CheckCircle2,
  Sun,
  Moon,
  Monitor,
  AlertTriangle,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Modal } from '../components/common/Modal';

type SettingsTab = 'profile' | 'appearance' | 'notifications' | 'preferences' | 'demo';

const mockAvatars = [
  'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&q=80',
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=150&q=80',
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=150&q=80',
  'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=150&q=80',
];

export const SettingsPage: React.FC = () => {
  const {
    userProfile,
    updateUserProfile,
    appSettings,
    updateAppSettings,
    setTheme,
    resetDemoData,
    addNotification,
  } = useApp();

  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');

  // Profile Form State
  const [username, setUsername] = useState(userProfile.username);
  const [displayName, setDisplayName] = useState(userProfile.displayName);
  const [email, setEmail] = useState(userProfile.email);
  const [avatar, setAvatar] = useState(userProfile.avatar);

  // Notifications State
  const [notifWorkerJoined, setNotifWorkerJoined] = useState(appSettings.notifications.workerJoined);
  const [notifStatusChanged, setNotifStatusChanged] = useState(appSettings.notifications.projectStatusChanged);
  const [notifCompleted, setNotifCompleted] = useState(appSettings.notifications.trainingCompleted);
  const [notifFailed, setNotifFailed] = useState(appSettings.notifications.trainingFailed);
  const [notifResourceWarning, setNotifResourceWarning] = useState(appSettings.notifications.resourceWarning);

  // App Preferences
  const [confirmDestructive, setConfirmDestructive] = useState(appSettings.appPreferences.confirmDestructiveActions);
  const [enableLiveUpdates, setEnableLiveUpdates] = useState(appSettings.appPreferences.enableLiveUpdates);
  const [simulationSpeed, setSimulationSpeed] = useState(appSettings.appPreferences.simulationSpeed);

  const [savedMessage, setSavedMessage] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);

  const handleSaveProfile = () => {
    updateUserProfile({ username, displayName, email, avatar });
    setSavedMessage(true);
    addNotification('Profile Updated', 'Your profile details were updated locally.', 'success');
    setTimeout(() => setSavedMessage(false), 3000);
  };

  const handleSavePreferences = () => {
    updateAppSettings({
      notifications: {
        workerJoined: notifWorkerJoined,
        projectStatusChanged: notifStatusChanged,
        trainingCompleted: notifCompleted,
        trainingFailed: notifFailed,
        resourceWarning: notifResourceWarning,
      },
      appPreferences: {
        ...appSettings.appPreferences,
        confirmDestructiveActions: confirmDestructive,
        enableLiveUpdates,
        simulationSpeed,
      },
    });
    setSavedMessage(true);
    addNotification('Preferences Saved', 'Application preferences have been saved.', 'success');
    setTimeout(() => setSavedMessage(false), 3000);
  };

  const handleResetData = () => {
    resetDemoData();
    setShowResetModal(false);
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }} className="animate-fade-in">
      {/* Header */}
      <div style={{ marginBottom: 26, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 14 }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 6 }}>
            Application Settings
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Customize your volunteer node profile, appearance themes, notifications, and simulation rules.
          </p>
        </div>

        {savedMessage && (
          <div
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--status-online-bg)',
              color: 'var(--status-online)',
              border: '1px solid var(--status-online-border)',
              fontSize: '0.85rem',
              fontWeight: 600,
            }}
          >
            Changes saved successfully!
          </div>
        )}
      </div>

      {/* Settings Container: Tabbed Sidebar + Content */}
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24 }} className="settings-layout">
        {/* Navigation Tabs */}
        <div
          className="card"
          style={{
            padding: 10,
            height: 'fit-content',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {[
            { id: 'profile', label: 'User Profile', icon: <User size={16} /> },
            { id: 'appearance', label: 'Appearance', icon: <Palette size={16} /> },
            { id: 'notifications', label: 'Notifications', icon: <Bell size={16} /> },
            { id: 'preferences', label: 'Preferences', icon: <Sliders size={16} /> },
            { id: 'demo', label: 'Data & Demo', icon: <RotateCcw size={16} /> },
          ].map((tab) => (
            <button
              key={tab.id}
              className={`btn ${activeTab === tab.id ? 'btn-primary' : 'btn-outline'}`}
              style={{
                width: '100%',
                justifyContent: 'flex-start',
                border: 'none',
                padding: '10px 14px',
                fontSize: '0.88rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: activeTab === tab.id ? 'var(--accent-primary)' : 'transparent',
                color: activeTab === tab.id ? '#ffffff' : 'var(--text-secondary)',
                boxShadow: activeTab === tab.id ? '0 2px 8px rgba(99, 102, 241, 0.3)' : 'none',
              }}
              onClick={() => setActiveTab(tab.id as SettingsTab)}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content Panes */}
        <div className="card" style={{ padding: '28px 32px' }}>
          {/* TAB 1: Profile */}
          {activeTab === 'profile' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 4 }}>
                  User Profile
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  This information identifies you when publishing projects as Master or joining as a Worker.
                </p>
              </div>

              {/* Avatar Selector */}
              <div>
                <label className="form-label">Profile Avatar</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 8 }}>
                  <img
                    src={avatar}
                    alt="Active Avatar"
                    style={{
                      width: 56,
                      height: 56,
                      borderRadius: '50%',
                      objectFit: 'cover',
                      border: '2px solid var(--accent-primary)',
                      boxShadow: '0 0 10px rgba(99, 102, 241, 0.3)',
                    }}
                  />
                  <div style={{ display: 'flex', gap: 10 }}>
                    {mockAvatars.map((avUrl, i) => (
                      <img
                        key={i}
                        src={avUrl}
                        alt={`Option ${i}`}
                        onClick={() => setAvatar(avUrl)}
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: '50%',
                          objectFit: 'cover',
                          cursor: 'pointer',
                          opacity: avatar === avUrl ? 1 : 0.6,
                          border: avatar === avUrl ? '2px solid var(--accent-primary)' : '1px solid var(--border-medium)',
                          transition: 'all var(--transition-fast)',
                        }}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Display Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Username Handle</label>
                <input
                  type="text"
                  className="form-input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Contact Email</label>
                <input
                  type="email"
                  className="form-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                <button className="btn btn-primary" onClick={handleSaveProfile}>
                  <Save size={16} />
                  <span>Save Profile</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: Appearance */}
          {activeTab === 'appearance' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 4 }}>
                  Appearance & Theme
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Select your preferred color theme. High contrast and electric neon accents.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
                {/* Dark Theme Card */}
                <div
                  className="card card-interactive"
                  onClick={() => setTheme('dark')}
                  style={{
                    padding: '20px',
                    borderColor: appSettings.theme === 'dark' ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    backgroundColor: '#0a0e17',
                    color: '#f8fafc',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                    boxShadow: appSettings.theme === 'dark' ? '0 0 15px rgba(99, 102, 241, 0.3)' : undefined,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Moon size={22} color="#818cf8" />
                    {appSettings.theme === 'dark' && <CheckCircle2 size={18} color="#818cf8" />}
                  </div>
                  <div>
                    <strong style={{ fontSize: '1rem', display: 'block' }}>Dark Theme (Default)</strong>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                      Deep charcoal slate with glowing violet/cyan accents
                    </span>
                  </div>
                </div>

                {/* Light Theme Card */}
                <div
                  className="card card-interactive"
                  onClick={() => setTheme('light')}
                  style={{
                    padding: '20px',
                    borderColor: appSettings.theme === 'light' ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    backgroundColor: '#ffffff',
                    color: '#0f172a',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                    boxShadow: appSettings.theme === 'light' ? '0 0 15px rgba(79, 70, 229, 0.2)' : undefined,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Sun size={22} color="#f59e0b" />
                    {appSettings.theme === 'light' && <CheckCircle2 size={18} color="#4f46e5" />}
                  </div>
                  <div>
                    <strong style={{ fontSize: '1rem', display: 'block', color: '#0f172a' }}>Light Theme</strong>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      Clean studio canvas with high-contrast text and crisp cards
                    </span>
                  </div>
                </div>

                {/* System Preference */}
                <div
                  className="card card-interactive"
                  onClick={() => setTheme('system')}
                  style={{
                    padding: '20px',
                    borderColor: appSettings.theme === 'system' ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Monitor size={22} color="var(--accent-cyan)" />
                    {appSettings.theme === 'system' && <CheckCircle2 size={18} color="var(--accent-cyan)" />}
                  </div>
                  <div>
                    <strong style={{ fontSize: '1rem', display: 'block' }}>System Sync</strong>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Match OS daylight / dark mode automatically
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Notifications */}
          {activeTab === 'notifications' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 4 }}>
                  Notification Rules
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Configure real-time event triggers for simulated cluster activity.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    backgroundColor: 'var(--bg-input)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <div>
                    <strong style={{ fontSize: '0.9rem', display: 'block' }}>Worker Node Joined Cluster</strong>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Notify when a new volunteer GPU/CPU connects to your master project.
                    </span>
                  </div>
                  <label className="switch-label">
                    <input
                      type="checkbox"
                      className="switch-input"
                      checked={notifWorkerJoined}
                      onChange={(e) => setNotifWorkerJoined(e.target.checked)}
                    />
                    <span className="switch-slider" />
                  </label>
                </div>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    backgroundColor: 'var(--bg-input)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <div>
                    <strong style={{ fontSize: '0.9rem', display: 'block' }}>Project Status Changed</strong>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Alert when training is paused, resumed, or terminated.
                    </span>
                  </div>
                  <label className="switch-label">
                    <input
                      type="checkbox"
                      className="switch-input"
                      checked={notifStatusChanged}
                      onChange={(e) => setNotifStatusChanged(e.target.checked)}
                    />
                    <span className="switch-slider" />
                  </label>
                </div>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    backgroundColor: 'var(--bg-input)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <div>
                    <strong style={{ fontSize: '0.9rem', display: 'block' }}>Training Job Completed</strong>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Notify when total training steps target has been reached.
                    </span>
                  </div>
                  <label className="switch-label">
                    <input
                      type="checkbox"
                      className="switch-input"
                      checked={notifCompleted}
                      onChange={(e) => setNotifCompleted(e.target.checked)}
                    />
                    <span className="switch-slider" />
                  </label>
                </div>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    backgroundColor: 'var(--bg-input)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <div>
                    <strong style={{ fontSize: '0.9rem', display: 'block' }}>Training Error / Failure Alert</strong>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Alert when gradient NaN divergence or node disconnection occurs.
                    </span>
                  </div>
                  <label className="switch-label">
                    <input
                      type="checkbox"
                      className="switch-input"
                      checked={notifFailed}
                      onChange={(e) => setNotifFailed(e.target.checked)}
                    />
                    <span className="switch-slider" />
                  </label>
                </div>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    backgroundColor: 'var(--bg-input)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <div>
                    <strong style={{ fontSize: '0.9rem', display: 'block' }}>Resource Budget Warnings</strong>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Alert if memory allocation approaches volunteer threshold limits.
                    </span>
                  </div>
                  <label className="switch-label">
                    <input
                      type="checkbox"
                      className="switch-input"
                      checked={notifResourceWarning}
                      onChange={(e) => setNotifResourceWarning(e.target.checked)}
                    />
                    <span className="switch-slider" />
                  </label>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                <button className="btn btn-primary" onClick={handleSavePreferences}>
                  <Save size={16} />
                  <span>Save Notification Preferences</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: Application Preferences */}
          {activeTab === 'preferences' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 4 }}>
                  Application Preferences
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Control simulation speeds and confirmation dialogues.
                </p>
              </div>

              {/* Live Updates Toggle */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '14px 16px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <strong style={{ fontSize: '0.9rem', display: 'block' }}>Enable Live Training Simulation</strong>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Simulates active gradient updates and step progress in the background.
                  </span>
                </div>
                <label className="switch-label">
                  <input
                    type="checkbox"
                    className="switch-input"
                    checked={enableLiveUpdates}
                    onChange={(e) => setEnableLiveUpdates(e.target.checked)}
                  />
                  <span className="switch-slider" />
                </label>
              </div>

              {/* Simulation Speed */}
              <div
                style={{
                  padding: '14px 16px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <strong style={{ fontSize: '0.9rem' }}>Simulation Speed Multiplier</strong>
                  <span className="mono" style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>
                    {simulationSpeed}x
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  {[1, 2, 5].map((speed) => (
                    <button
                      key={speed}
                      className={`btn btn-sm ${simulationSpeed === speed ? 'btn-primary' : 'btn-outline'}`}
                      style={{ flex: 1 }}
                      onClick={() => setSimulationSpeed(speed)}
                    >
                      {speed}x {speed === 1 ? '(Normal)' : speed === 2 ? '(Fast)' : '(Hyper)'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Confirm Destructive Actions */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '14px 16px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <strong style={{ fontSize: '0.9rem', display: 'block' }}>Confirm Destructive Actions</strong>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Prompt confirmation modals before stopping projects or disconnecting nodes.
                  </span>
                </div>
                <label className="switch-label">
                  <input
                    type="checkbox"
                    className="switch-input"
                    checked={confirmDestructive}
                    onChange={(e) => setConfirmDestructive(e.target.checked)}
                  />
                  <span className="switch-slider" />
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                <button className="btn btn-primary" onClick={handleSavePreferences}>
                  <Save size={16} />
                  <span>Save Preferences</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 5: Data & Demo Settings */}
          {activeTab === 'demo' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 4 }}>
                  Data & Demo Settings
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Manage stored local storage state or restore pristine sample dataset catalog.
                </p>
              </div>

              <div className="alert-box alert-warning">
                <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <strong>Reset Warning</strong>
                  <p style={{ marginTop: 2, fontSize: '0.84rem' }}>
                    Resetting will clear all created projects, active worker contributions, and customized
                    settings, restoring the initial pristine prototype state.
                  </p>
                </div>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '18px 20px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div>
                  <strong style={{ fontSize: '1rem', display: 'block' }}>Reset All Demo Data</strong>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Restores mock projects, default volunteer workers, and clears role assignments.
                  </span>
                </div>

                <button
                  className="btn btn-danger"
                  onClick={() => setShowResetModal(true)}
                >
                  <RotateCcw size={16} />
                  <span>Reset Demo Data</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Reset Confirmation Modal */}
      <Modal
        isOpen={showResetModal}
        onClose={() => setShowResetModal(false)}
        title="Reset Demo State?"
        variant="danger"
        confirmLabel="Reset to Clean State"
        onConfirm={handleResetData}
      >
        <p>
          Are you sure you want to reset all mock projects and local state?
        </p>
        <p style={{ marginTop: 8, fontSize: '0.88rem' }}>
          This will clear browser localStorage, reload the default projects catalog, and reset your role
          to unassigned.
        </p>
      </Modal>
    </div>
  );
};
