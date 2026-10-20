import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import type { MetricHistoryPoint } from '../../types';
import { TrendingDown, Gauge, Zap, HardDrive } from 'lucide-react';

interface TrainingChartsProps {
  history: MetricHistoryPoint[];
}

type ChartTab = 'loss' | 'speed' | 'hardware' | 'memory';

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number | string;
    color?: string;
  }>;
  label?: string;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div
        style={{
          backgroundColor: 'var(--bg-card-elevated)',
          border: '1px solid var(--border-medium)',
          borderRadius: 'var(--radius-md)',
          padding: '10px 14px',
          boxShadow: 'var(--shadow-md)',
          fontSize: '0.8rem',
        }}
      >
        <p style={{ color: 'var(--text-muted)', marginBottom: 6 }}>
          Step: <strong style={{ color: 'var(--text-primary)' }}>{label}</strong>
        </p>
        {payload.map((entry, index) => (
          <div
            key={`tooltip-${index}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginTop: 3,
              color: entry.color || 'var(--text-primary)',
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: entry.color || 'var(--accent-primary)',
              }}
            />
            <span>{entry.name}:</span>
            <strong className="mono">{entry.value}</strong>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export const TrainingCharts: React.FC<TrainingChartsProps> = ({ history }) => {
  const [activeTab, setActiveTab] = useState<ChartTab>('loss');

  return (
    <div className="card" style={{ padding: '20px 24px' }}>
      {/* Chart Header & Selectors */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          marginBottom: 20,
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: 16,
        }}
      >
        <div>
          <h4 style={{ fontSize: '1.05rem', fontWeight: 600, margin: 0 }}>
            Cluster Training Metrics
          </h4>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Real-time telemetry aggregated across connected volunteer worker nodes
          </span>
        </div>

        {/* Tab Buttons */}
        <div
          style={{
            display: 'flex',
            backgroundColor: 'var(--bg-input)',
            padding: 3,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            gap: 2,
          }}
        >
          <button
            className={`btn btn-sm ${activeTab === 'loss' ? 'btn-primary' : 'btn-outline'}`}
            style={{
              border: 'none',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              boxShadow: activeTab === 'loss' ? undefined : 'none',
            }}
            onClick={() => setActiveTab('loss')}
          >
            <TrendingDown size={14} />
            Loss Curve
          </button>

          <button
            className={`btn btn-sm ${activeTab === 'speed' ? 'btn-primary' : 'btn-outline'}`}
            style={{
              border: 'none',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              boxShadow: activeTab === 'speed' ? undefined : 'none',
            }}
            onClick={() => setActiveTab('speed')}
          >
            <Gauge size={14} />
            Throughput
          </button>

          <button
            className={`btn btn-sm ${activeTab === 'hardware' ? 'btn-primary' : 'btn-outline'}`}
            style={{
              border: 'none',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              boxShadow: activeTab === 'hardware' ? undefined : 'none',
            }}
            onClick={() => setActiveTab('hardware')}
          >
            <Zap size={14} />
            Compute Util
          </button>

          <button
            className={`btn btn-sm ${activeTab === 'memory' ? 'btn-primary' : 'btn-outline'}`}
            style={{
              border: 'none',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              boxShadow: activeTab === 'memory' ? undefined : 'none',
            }}
            onClick={() => setActiveTab('memory')}
          >
            <HardDrive size={14} />
            Cluster RAM
          </button>
        </div>
      </div>

      {/* Chart Display Area */}
      <div style={{ height: 280, width: '100%' }}>
        <ResponsiveContainer width="100%" height="100%">
          {activeTab === 'loss' ? (
            <AreaChart data={history} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="lossGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
              <XAxis dataKey="step" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} domain={['dataMin - 0.02', 'dataMax + 0.05']} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="loss"
                name="Validation Loss"
                stroke="#6366f1"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#lossGradient)"
              />
            </AreaChart>
          ) : activeTab === 'speed' ? (
            <LineChart data={history} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
              <XAxis dataKey="step" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} unit=" s/s" />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="speed"
                name="Speed (Steps/sec)"
                stroke="#06b6d4"
                strokeWidth={2.5}
                dot={false}
              />
            </LineChart>
          ) : activeTab === 'hardware' ? (
            <LineChart data={history} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
              <XAxis dataKey="step" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} unit="%" domain={[0, 100]} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="clusterGpuUtil"
                name="GPU Load (%)"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="clusterCpuUtil"
                name="CPU Load (%)"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          ) : (
            <AreaChart data={history} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="ramGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ec4899" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#ec4899" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
              <XAxis dataKey="step" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} unit=" GB" />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="ramUtilGB"
                name="Cluster Allocated RAM"
                stroke="#ec4899"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#ramGradient)"
              />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Metric Indicators below chart */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: 12,
          marginTop: 18,
          paddingTop: 16,
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '0.8rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#6366f1' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>Loss Value</span>
            <strong className="mono" style={{ fontSize: '0.9rem' }}>
              {history.length > 0 ? history[history.length - 1].loss.toFixed(4) : '0.0000'}
            </strong>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#06b6d4' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>Cluster Speed</span>
            <strong className="mono" style={{ fontSize: '0.9rem' }}>
              {history.length > 0 ? history[history.length - 1].speed : '0'} steps/s
            </strong>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#10b981' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>Avg GPU Load</span>
            <strong className="mono" style={{ fontSize: '0.9rem' }}>
              {history.length > 0 ? history[history.length - 1].clusterGpuUtil : '0'}%
            </strong>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: '#f59e0b' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>Avg CPU Load</span>
            <strong className="mono" style={{ fontSize: '0.9rem' }}>
              {history.length > 0 ? history[history.length - 1].clusterCpuUtil : '0'}%
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
};
