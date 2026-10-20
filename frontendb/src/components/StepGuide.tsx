import React from 'react';
import { Download, Terminal, UserCheck, Globe } from 'lucide-react';
import { useApp } from '../context/AppContext';

export const StepGuide: React.FC = () => {
  const { simulateRoleConnection } = useApp();

  const handleDownload = () => {
    // Placeholder download demo action
    const link = document.createElement('a');
    link.href = '#';
    link.setAttribute('download', 'adc-agent-installer.exe');
    // alert or prompt
    window.open('https://github.com', '_blank');
  };

  return (
    <div className="startup-view">
      <h1 className="startup-heading">Welcome to ADC</h1>

      <div className="steps-list">
        {/* Step 1 */}
        <div className="step-item">
          <div className="step-number">1</div>
          <div className="step-content">
            <h3 className="step-title">Download the ADC app</h3>
            <p className="step-desc">
              Download and install the native ADC background client on your desktop or server.
            </p>
            <div className="step-action-row">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleDownload}
              >
                <Download size={14} />
                <span>Download ADC App</span>
              </button>
            </div>
          </div>
        </div>

        {/* Step 2 */}
        <div className="step-item">
          <div className="step-number">2</div>
          <div className="step-content">
            <h3 className="step-title">Run the application</h3>
            <p className="step-desc">
              Launch the installed ADC application executable to initialize your local daemon.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
              <Terminal size={14} />
              <span>Client runs locally in your tray or terminal</span>
            </div>
          </div>
        </div>

        {/* Step 3 */}
        <div className="step-item">
          <div className="step-number">3</div>
          <div className="step-content">
            <h3 className="step-title">Choose a role</h3>
            <p className="step-desc">
              Select whether you want to orchestrate training (Master) or contribute compute power (Worker) in the app.
            </p>
            <div className="step-action-row">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => simulateRoleConnection('master')}
              >
                <UserCheck size={14} />
                <span>Simulate App: Connect as Master</span>
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => simulateRoleConnection('worker')}
              >
                <UserCheck size={14} />
                <span>Simulate App: Connect as Worker</span>
              </button>
            </div>
          </div>
        </div>

        {/* Step 4 */}
        <div className="step-item">
          <div className="step-number">4</div>
          <div className="step-content">
            <h3 className="step-title">Open the website</h3>
            <p className="step-desc">
              Return to this dashboard after connecting your app to configure or join your training cluster.
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
              <Globe size={14} />
              <span>Awaiting agent registration handshake...</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
