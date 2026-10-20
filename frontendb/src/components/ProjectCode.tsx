import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { formatProjectCode } from '../utils/formatting';

interface ProjectCodeProps {
  code: string;
  label?: string;
  showCopy?: boolean;
}

export const ProjectCode: React.FC<ProjectCodeProps> = ({
  code,
  label = 'Project Code',
  showCopy = true
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code.replace(/\D/g, ''));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      {label && <span className="metric-label">{label}</span>}
      <div className="project-code-box">
        <span className="project-code-text">{formatProjectCode(code)}</span>
        {showCopy && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleCopy}
            title="Copy project code"
            style={{ padding: '4px 8px', fontSize: '12px' }}
          >
            {copied ? (
              <>
                <Check size={14} color="#10a37f" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy size={14} />
                <span>Copy</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
