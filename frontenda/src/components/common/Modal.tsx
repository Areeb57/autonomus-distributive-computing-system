import React, { useEffect } from 'react';
import { X, AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void;
  variant?: 'danger' | 'warning' | 'primary' | 'info';
  confirmLoading?: boolean;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  variant = 'primary',
  confirmLoading = false,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {variant === 'danger' && <AlertCircle size={20} color="var(--status-stopped)" />}
            {variant === 'warning' && <AlertTriangle size={20} color="var(--status-paused)" />}
            {variant === 'info' && <Info size={20} color="var(--accent-primary)" />}
            {variant === 'primary' && <CheckCircle2 size={20} color="var(--status-online)" />}
            <h3 style={{ fontSize: '1.1rem', margin: 0 }}>{title}</h3>
          </div>
          <button
            className="btn-icon"
            onClick={onClose}
            aria-label="Close modal"
            style={{ width: 32, height: 32 }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">{children}</div>

        <div className="modal-footer">
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={confirmLoading}>
            {cancelLabel}
          </button>
          {onConfirm && (
            <button
              className={`btn ${
                variant === 'danger'
                  ? 'btn-danger'
                  : variant === 'warning'
                  ? 'btn-danger'
                  : 'btn-primary'
              } btn-sm`}
              onClick={() => {
                onConfirm();
              }}
              disabled={confirmLoading}
            >
              {confirmLoading ? 'Processing...' : confirmLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
