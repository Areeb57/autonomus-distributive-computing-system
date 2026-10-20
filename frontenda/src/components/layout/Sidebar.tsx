import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Layers,
  Activity,
  Cpu,
  Settings,
  Sparkles,
  Server,
  Zap,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Badge } from '../common/Badge';

interface SidebarProps {
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ mobileOpen = false, onCloseMobile }) => {
  const { currentUserRole, activeProject } = useApp();
  const navigate = useNavigate();

  const navItems = [
    {
      to: '/',
      label: 'Dashboard',
      icon: <LayoutDashboard size={19} />,
    },
    {
      to: '/projects',
      label: 'Projects',
      icon: <Layers size={19} />,
    },
    {
      to: activeProject ? `/projects/${activeProject.id}` : '/my-project',
      label: 'My Project',
      icon: <Activity size={19} />,
      badge: activeProject ? activeProject.name : undefined,
      isHighlighted: !!activeProject,
    },
    {
      to: '/resources',
      label: 'Resource Settings',
      icon: <Cpu size={19} />,
    },
    {
      to: '/settings',
      label: 'Settings',
      icon: <Settings size={19} />,
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          onClick={onCloseMobile}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(4px)',
            zIndex: 99,
          }}
        />
      )}

      <aside
        style={{
          width: 'var(--sidebar-width)',
          backgroundColor: 'var(--bg-sidebar)',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 100,
          transition: 'transform var(--transition-normal)',
          transform: mobileOpen ? 'translateX(0)' : undefined,
        }}
        className={`sidebar-container ${mobileOpen ? 'open' : ''}`}
      >
        {/* Brand / Logo */}
        <div
          onClick={() => {
            navigate('/');
            onCloseMobile?.();
          }}
          style={{
            height: 'var(--topbar-height)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '0 20px',
            borderBottom: '1px solid var(--border-subtle)',
            cursor: 'pointer',
          }}
        >
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)',
            }}
          >
            <Sparkles size={20} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span
              style={{
                fontWeight: 700,
                fontSize: '0.98rem',
                letterSpacing: '-0.02em',
                color: 'var(--text-primary)',
                lineHeight: 1.15,
              }}
            >
              Autonomous AI
            </span>
            <span
              style={{
                fontSize: '0.72rem',
                color: 'var(--text-muted)',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                fontWeight: 600,
              }}
            >
              Distributed Trainer
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav
          style={{
            flex: 1,
            padding: '20px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            overflowY: 'auto',
          }}
        >
          <div
            style={{
              fontSize: '0.72rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              color: 'var(--text-muted)',
              padding: '0 10px 6px',
            }}
          >
            Navigation
          </div>

          {navItems.map((item) => (
            <NavLink
              key={item.label}
              to={item.to}
              end={item.to === '/'}
              onClick={onCloseMobile}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? '#ffffff' : 'var(--text-secondary)',
                backgroundColor: isActive
                  ? 'var(--accent-primary)'
                  : item.isHighlighted
                  ? 'rgba(99, 102, 241, 0.08)'
                  : 'transparent',
                boxShadow: isActive ? '0 2px 10px rgba(99, 102, 241, 0.35)' : 'none',
                transition: 'all var(--transition-fast)',
              })}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                {item.icon}
                <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                  {item.label}
                </span>
              </div>

              {item.badge && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: 'rgba(255, 255, 255, 0.15)',
                    color: '#ffffff',
                    maxWidth: 80,
                    textOverflow: 'ellipsis',
                    overflow: 'hidden',
                    whiteSpace: 'nowrap',
                  }}
                  title={item.badge}
                >
                  Active
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Node Status Box at Sidebar Bottom */}
        <div
          style={{
            padding: 16,
            borderTop: '1px solid var(--border-subtle)',
            backgroundColor: 'rgba(0, 0, 0, 0.12)',
          }}
        >
          <div
            style={{
              padding: 12,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-card-hover)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Server size={14} color="var(--accent-primary)" />
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Local Node Status
                </span>
              </div>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: 'var(--status-online)',
                  boxShadow: '0 0 6px var(--status-online)',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Role:</span>
              <Badge role={currentUserRole} />
            </div>

            {activeProject ? (
              <div
                style={{
                  fontSize: '0.72rem',
                  color: 'var(--text-secondary)',
                  borderTop: '1px solid var(--border-subtle)',
                  paddingTop: 6,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <Zap size={12} color="var(--status-online)" />
                <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                  {activeProject.name}
                </span>
              </div>
            ) : (
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                No active job attached
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};
