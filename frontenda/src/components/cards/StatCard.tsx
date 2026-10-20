import React from 'react';

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  icon?: React.ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
    isNeutral?: boolean;
  };
  highlight?: boolean;
  demoBadge?: boolean;
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subValue,
  icon,
  trend,
  highlight = false,
  demoBadge = false,
  className = '',
}) => {
  return (
    <div
      className={`card ${highlight ? 'card-glow' : ''} ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '18px 20px',
        position: 'relative',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 12,
        }}
      >
        <span
          style={{
            fontSize: '0.82rem',
            fontWeight: 500,
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {label}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {demoBadge && (
            <span
              style={{
                fontSize: '0.68rem',
                padding: '2px 6px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              Demo
            </span>
          )}
          {icon && (
            <div
              style={{
                padding: 6,
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--accent-primary-light)',
                color: 'var(--accent-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {icon}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span
          className="mono"
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            lineHeight: 1.1,
          }}
        >
          {value}
        </span>
        {subValue && (
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {subValue}
          </span>
        )}
      </div>

      {trend && (
        <div
          style={{
            marginTop: 10,
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            color: trend.isNeutral
              ? 'var(--text-muted)'
              : trend.isPositive
              ? 'var(--status-online)'
              : 'var(--status-stopped)',
          }}
        >
          <span>{trend.isPositive ? '↑' : trend.isNeutral ? '•' : '↓'}</span>
          <span>{trend.value}</span>
        </div>
      )}
    </div>
  );
};
