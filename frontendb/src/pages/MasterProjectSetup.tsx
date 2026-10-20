import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { FileUpload } from '../components/FileUpload';
import { ArrowRight } from 'lucide-react';

export const MasterProjectSetup: React.FC = () => {
  const navigate = useNavigate();
  const { pendingMasterDraft, saveMasterDraft, masterProject } = useApp();

  const [name, setName] = useState(pendingMasterDraft?.name || masterProject?.name || '');
  const [description, setDescription] = useState(
    pendingMasterDraft?.description || masterProject?.description || ''
  );
  const [datasetFileName, setDatasetFileName] = useState(
    pendingMasterDraft?.datasetFileName || masterProject?.datasetFileName || ''
  );
  const [datasetFileSize, setDatasetFileSize] = useState(
    pendingMasterDraft?.datasetFileSize || masterProject?.datasetFileSize || ''
  );
  const [codeFileName, setCodeFileName] = useState(
    pendingMasterDraft?.codeFileName || masterProject?.codeFileName || ''
  );
  const [codeFileSize, setCodeFileSize] = useState(
    pendingMasterDraft?.codeFileSize || masterProject?.codeFileSize || ''
  );

  const [errors, setErrors] = useState<{
    name?: string;
    dataset?: string;
    code?: string;
  }>({});

  const validate = () => {
    const errs: typeof errors = {};
    if (!name.trim()) {
      errs.name = 'Project name is required';
    }
    if (!datasetFileName) {
      errs.dataset = 'Dataset file is required';
    }
    if (!codeFileName) {
      errs.code = 'Model training code file is required';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    saveMasterDraft({
      name: name.trim(),
      description: description.trim(),
      datasetFileName,
      datasetFileSize,
      codeFileName,
      codeFileSize
    });

    navigate('/master/review');
  };

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 600 }}>Create Training Project</h1>
      </div>

      <form onSubmit={handleSubmit} className="setup-form">
        {/* Project Name */}
        <div className="form-group">
          <label htmlFor="projectName" className="form-label">
            <span>
              Project Name <span style={{ color: '#ef4444' }}>*</span>
            </span>
          </label>
          <input
            type="text"
            id="projectName"
            placeholder="e.g. Llama-3-8B Fine-tuning"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (errors.name) setErrors({ ...errors, name: undefined });
            }}
          />
          {errors.name && <span className="input-error">{errors.name}</span>}
        </div>

        {/* Project Description (Optional) */}
        <div className="form-group">
          <label htmlFor="projectDesc" className="form-label">
            <span>Project Description</span>
            <span className="form-helper">Optional</span>
          </label>
          <textarea
            id="projectDesc"
            rows={3}
            placeholder="Brief overview of model hyperparameters, objective, or cluster notes"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* Dataset File Upload */}
        <div>
          <FileUpload
            id="dataset-upload"
            label="Dataset File"
            accept=".zip,.tar,.gz,.csv,.parquet,.json,.jsonl"
            helperText=".zip, .parquet, .csv, .jsonl"
            fileName={datasetFileName}
            fileSize={datasetFileSize}
            demoDefault={{ name: 'pubmed_dataset.parquet', size: '1.4 GB' }}
            onFileSelect={(fName, fSize) => {
              setDatasetFileName(fName);
              setDatasetFileSize(fSize);
              if (errors.dataset) setErrors({ ...errors, dataset: undefined });
            }}
            onFileClear={() => {
              setDatasetFileName('');
              setDatasetFileSize('');
            }}
            required
          />
          {errors.dataset && <span className="input-error">{errors.dataset}</span>}
        </div>

        {/* Model Training Code File Upload */}
        <div>
          <FileUpload
            id="code-upload"
            label="Model Training Code"
            accept=".py,.zip,.tar.gz"
            helperText=".py scripts or code archive"
            fileName={codeFileName}
            fileSize={codeFileSize}
            demoDefault={{ name: 'train_lora_ddp.py', size: '42.8 KB' }}
            onFileSelect={(fName, fSize) => {
              setCodeFileName(fName);
              setCodeFileSize(fSize);
              if (errors.code) setErrors({ ...errors, code: undefined });
            }}
            onFileClear={() => {
              setCodeFileName('');
              setCodeFileSize('');
            }}
            required
          />
          {errors.code && <span className="input-error">{errors.code}</span>}
        </div>

        {/* Action Button */}
        <div className="form-actions">
          <button type="submit" className="btn btn-primary">
            <span>Review Project</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
    </div>
  );
};
