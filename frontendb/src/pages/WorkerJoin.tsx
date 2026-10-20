import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { formatProjectCode, cleanProjectCode } from '../utils/formatting';
import { ArrowRight, LoaderCircle, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';

export const WorkerJoin: React.FC = () => {
  const navigate = useNavigate();
  const { setPendingWorkerCode, masterProject, backendOnline } = useApp();

  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isResolving, setIsResolving] = useState(false);
  const [resolvedMaster, setResolvedMaster] = useState<{ projectId: string; masterAgentId: string; projectName?: string } | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 9);
    setCode(raw);
    if (error) setError(null);
  };

  const handleUseMasterCode = () => {
    if (masterProject?.projectCode) {
      setCode(masterProject.projectCode);
      if (error) setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = cleanProjectCode(code);

    if (clean.length !== 9) {
      setError('Please enter a valid 9-digit project code.');
      return;
    }

    setIsResolving(true);
    setError(null);
    setResolvedMaster(null);
    try {
      // Online mode resolves the code through the backend so the browser never guesses
      // the master's address or invents the WebRTC authorization token.
      if (backendOnline) {
        const master = await api.resolveWebRtcProjectCode(clean);
        setResolvedMaster(master);
      } else if (masterProject && masterProject.projectCode && masterProject.projectCode !== clean) {
        setError(`Project ${clean} not found. Active demo project code is ${formatProjectCode(masterProject.projectCode)}.`);
        return;
      }

      setPendingWorkerCode(clean);
      navigate('/worker/allocation');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not resolve this project code.');
    } finally {
      setIsResolving(false);
    }
  };

  return (
    <div className="page-container centered">
      <div className="join-container">
        <h1 style={{ fontSize: '22px', fontWeight: 600, marginBottom: '8px' }}>
          Join a Project
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          Enter the 9-digit project code provided by your cluster Master.
        </p>

        <form onSubmit={handleSubmit} className="code-input-group">
          <div>
            <input
              type="text"
              className="code-input"
              placeholder="000 000 000"
              value={formatProjectCode(code)}
              onChange={handleInputChange}
              maxLength={11}
              autoFocus
            />
            {error && <p className="input-error">{error}</p>}
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={code.length !== 9 || isResolving}
          >
            {isResolving ? <><LoaderCircle size={16} className="spin" /><span>Finding Master…</span></> : <><span>Enter</span><ArrowRight size={16} /></>}
          </button>
        </form>

        {resolvedMaster && (
          <div role="status" style={{ marginTop: 16, padding: '12px 14px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', fontSize: 12 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
              <ShieldCheck size={15} /> <strong>Master found</strong>
            </div>
            <div style={{ color: 'var(--text-secondary)' }}>Project ID: {resolvedMaster.projectId}</div>
            <div style={{ color: 'var(--text-secondary)' }}>Master agent: {resolvedMaster.masterAgentId}</div>
            <div style={{ color: 'var(--text-secondary)', marginTop: 4 }}>Connection credentials are ready. The worker agent will be contacted after you confirm resource allocation.</div>
          </div>
        )}

        {!backendOnline && (
          <p style={{ marginTop: 14, color: 'var(--text-secondary)', fontSize: 12 }}>
            Demo/offline mode: the website cannot resolve a master on another computer until its backend signaling API is online.
          </p>
        )}

        {masterProject?.projectCode && (
          <div
            style={{
              marginTop: '16px',
              padding: '10px 14px',
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <span style={{ color: 'var(--text-secondary)' }}>
              Online Demo Master: <strong>{formatProjectCode(masterProject.projectCode)}</strong>
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleUseMasterCode}
              style={{ padding: '3px 8px', fontSize: '11px' }}
            >
              Fill Code
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
