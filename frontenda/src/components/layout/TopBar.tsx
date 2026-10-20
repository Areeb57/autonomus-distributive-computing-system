import React, { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Bell,
  Sun,
  Moon,
  Menu,
  RotateCcw,
  User,
  Check,
  Trash2,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Badge } from '../common/Badge';

interface TopBarProps {
  onToggleMobileSidebar: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onToggleMobileSidebar }) => {
  const {
    currentUserRole,
    userProfile,
    appSettings,
    setTheme,
    notifications,
    unreadNotificationCount,
    markNotificationRead,
    markAllNotificationsRead,
    clearAllNotifications,
    resetDemoData,
  } = useApp();

  const location = useLocation();
  const navigate = useNavigate();

  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
      if (userRef.current && !userRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Compute page title
  const getPageTitle = () => {
    const path = location.pathname;
    if (path === '/') return 'Dashboard';
    if (path === '/projects') return 'Project Discovery';
    if (path.startsWith('/create-project')) return 'Start New Project as Master';
    if (path.startsWith('/projects/')) return 'Project Progress & Telemetry';
    if (path === '/my-project') return 'My Project';
    if (path.startsWith('/worker-setup/')) return 'Worker Agent Setup';
    if (path.startsWith('/worker-hardware/')) return 'Hardware Profiling';
    if (path.startsWith('/worker-resources/')) return 'Resource Contribution';
    if (path === '/resources') return 'Resource Settings';
    if (path === '/settings') return 'Application Settings';
    return 'Autonomous Distributed AI Trainer';
  };

  const isDarkMode =
    appSettings.theme === 'dark' ||
    (appSettings.theme === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);

  const toggleTheme = () => {
    setTheme(isDarkMode ? 'light' : 'dark');
  };

  return (
    <header
      style={{
        height: 'var(--topbar-height)',
        backgroundColor: 'var(--bg-topbar)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      {/* Left Title & Mobile Menu button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <button
          className="btn-icon mobile-menu-btn"
          onClick={onToggleMobileSidebar}
          aria-label="Open navigation menu"
          style={{ display: 'none' }}
        >
          <Menu size={20} />
        </button>

        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          {getPageTitle()}
        </h2>
      </div>

      {/* Right Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {/* Persistent Role Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'none' }} className="role-label">
            Role:
          </span>
          <Badge role={currentUserRole} />
        </div>

        {/* Theme Toggle Button */}
        <button
          className="btn-icon"
          onClick={toggleTheme}
          title={`Switch to ${isDarkMode ? 'Light' : 'Dark'} Theme`}
          aria-label="Toggle theme"
        >
          {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Notifications Dropdown */}
        <div style={{ position: 'relative' }} ref={notifRef}>
          <button
            className="btn-icon"
            onClick={() => setShowNotifications(!showNotifications)}
            title="Notifications"
            aria-label="View notifications"
            style={{ position: 'relative' }}
          >
            <Bell size={18} />
            {unreadNotificationCount > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: 6,
                  right: 6,
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: 'var(--status-online)',
                  boxShadow: '0 0 6px var(--status-online)',
                }}
              />
            )}
          </button>

          {showNotifications && (
            <div
              style={{
                position: 'absolute',
                top: 48,
                right: 0,
                width: 340,
                backgroundColor: 'var(--bg-card-elevated)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-lg)',
                boxShadow: 'var(--shadow-lg)',
                zIndex: 100,
                overflow: 'hidden',
                animation: 'modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Notifications</span>
                  {unreadNotificationCount > 0 && (
                    <span
                      style={{
                        fontSize: '0.72rem',
                        padding: '1px 6px',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: 'var(--accent-primary)',
                        color: '#ffffff',
                      }}
                    >
                      {unreadNotificationCount}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    onClick={markAllNotificationsRead}
                    title="Mark all as read"
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--accent-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Check size={13} />
                    Mark Read
                  </button>
                  <button
                    onClick={clearAllNotifications}
                    title="Clear notifications"
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--text-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                {notifications.length === 0 ? (
                  <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    No notifications
                  </div>
                ) : (
                  notifications.map((notif) => (
                    <div
                      key={notif.id}
                      onClick={() => {
                        markNotificationRead(notif.id);
                        if (notif.projectId) navigate(`/projects/${notif.projectId}`);
                        setShowNotifications(false);
                      }}
                      style={{
                        padding: '10px 16px',
                        borderBottom: '1px solid var(--border-subtle)',
                        backgroundColor: notif.read ? 'transparent' : 'rgba(99, 102, 241, 0.06)',
                        cursor: 'pointer',
                        transition: 'background var(--transition-fast)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: notif.read ? 500 : 600, color: 'var(--text-primary)' }}>
                          {notif.title}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          {notif.timestamp}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.35 }}>
                        {notif.message}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Account Menu */}
        <div style={{ position: 'relative' }} ref={userRef}>
          <div
            onClick={() => setShowUserMenu(!showUserMenu)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '4px 8px 4px 4px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
          >
            <img
              src={userProfile.avatar}
              alt={userProfile.displayName}
              style={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                objectFit: 'cover',
                border: '1px solid var(--accent-primary)',
              }}
            />
            <span
              style={{
                fontSize: '0.84rem',
                fontWeight: 500,
                color: 'var(--text-primary)',
                maxWidth: 110,
                textOverflow: 'ellipsis',
                overflow: 'hidden',
                whiteSpace: 'nowrap',
              }}
              className="user-name-label"
            >
              {userProfile.displayName}
            </span>
          </div>

          {showUserMenu && (
            <div
              style={{
                position: 'absolute',
                top: 48,
                right: 0,
                width: 240,
                backgroundColor: 'var(--bg-card-elevated)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-lg)',
                boxShadow: 'var(--shadow-lg)',
                zIndex: 100,
                overflow: 'hidden',
                animation: 'modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.88rem', fontWeight: 600, display: 'block' }}>
                  {userProfile.displayName}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>
                  {userProfile.email}
                </span>
              </div>

              <div style={{ padding: 6, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <button
                  className="btn btn-secondary btn-sm"
                  style={{
                    width: '100%',
                    justifyContent: 'flex-start',
                    border: 'none',
                    backgroundColor: 'transparent',
                  }}
                  onClick={() => {
                    navigate('/settings');
                    setShowUserMenu(false);
                  }}
                >
                  <User size={15} />
                  Profile & Preferences
                </button>

                <button
                  className="btn btn-secondary btn-sm"
                  style={{
                    width: '100%',
                    justifyContent: 'flex-start',
                    border: 'none',
                    backgroundColor: 'transparent',
                    color: 'var(--status-paused)',
                  }}
                  onClick={() => {
                    resetDemoData();
                    setShowUserMenu(false);
                  }}
                >
                  <RotateCcw size={15} />
                  Reset Demo State
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
