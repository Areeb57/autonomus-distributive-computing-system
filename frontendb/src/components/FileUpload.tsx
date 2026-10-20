import React, { useRef } from 'react';
import { UploadCloud, File, X } from 'lucide-react';
import { formatBytes } from '../utils/formatting';

interface FileUploadProps {
  id: string;
  label: string;
  accept: string;
  helperText?: string;
  fileName?: string;
  fileSize?: string;
  onFileSelect: (name: string, size: string) => void;
  onFileClear: () => void;
  required?: boolean;
  demoDefault?: { name: string; size: string };
}

export const FileUpload: React.FC<FileUploadProps> = ({
  id,
  label,
  accept,
  helperText,
  fileName,
  fileSize,
  onFileSelect,
  onFileClear,
  required = false,
  demoDefault
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect(file.name, formatBytes(file.size));
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) {
      onFileSelect(file.name, formatBytes(file.size));
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  return (
    <div className="form-group">
      <div className="form-label">
        <span>
          {label} {required && <span style={{ color: '#ef4444' }}>*</span>}
        </span>
        {helperText && <span className="form-helper">{helperText}</span>}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        id={id}
        accept={accept}
        onChange={handleFileChange}
        className="sr-only"
      />

      {fileName ? (
        <div className="file-selected-badge">
          <div className="file-selected-info">
            <File size={16} color="var(--text-secondary)" />
            <span>{fileName}</span>
            {fileSize && (
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                ({fileSize})
              </span>
            )}
          </div>
          <button
            type="button"
            className="btn-icon"
            onClick={() => {
              onFileClear();
              if (fileInputRef.current) fileInputRef.current.value = '';
            }}
            title="Remove file"
            style={{ padding: '4px' }}
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div
          className="file-dropzone"
          onClick={() => fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          role="button"
          tabIndex={0}
        >
          <div className="file-dropzone-content">
            <UploadCloud size={20} color="var(--text-muted)" />
            <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
              Choose file or drag & drop
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Accepted formats: {accept}
            </span>
            {demoDefault && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ marginTop: '4px', fontSize: '11px', padding: '3px 8px' }}
                onClick={(e) => {
                  e.stopPropagation();
                  onFileSelect(demoDefault.name, demoDefault.size);
                }}
              >
                Use sample {demoDefault.name} ({demoDefault.size})
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
