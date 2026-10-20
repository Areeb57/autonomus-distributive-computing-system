import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileCode,
  Database,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Trash2,
  AlertCircle,
  Sparkles,
  Info,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Stepper } from '../components/progress/Stepper';
import type { StepItem } from '../components/progress/Stepper';
import { Modal } from '../components/common/Modal';

export const CreateProjectPage: React.FC = () => {
  const navigate = useNavigate();
  const { createProject } = useApp();

  const [currentStep, setCurrentStep] = useState(1);

  // Step 1: Project Information State
  const [formData, setFormData] = useState({
    name: 'Latent Diffusion Model from Scratch',
    description: 'A distributed 180M parameter latent diffusion model trained on synthetic manifold image patches with classifier-free guidance.',
    trainingObjective: 'Train latent diffusion UNet from scratch on synthetic manifolds with classifier-free guidance.',
    modelArchitecture: 'Diffusion (UNet / DiT 180M)',
    datasetName: 'TinyImageNet-Manifold-200k',
    datasetDescription: '200,000 augmented images normalized to 64x64 FP16 tensors.',
    expectedDuration: '4 hours 30 mins',
    visibility: 'public' as 'public' | 'unlisted',
    workersNeeded: 6,
    // Training config
    batchSize: 128,
    totalSteps: 10000,
    learningRate: '2e-4',
    optimizer: 'AdamW (beta1=0.9, beta2=0.999)',
    precision: 'fp16' as 'fp16' | 'bf16' | 'fp32',
    checkpointInterval: 500,
    gradientAccumulationSteps: 2,
  });

  // Step 2: Upload Files State
  const [datasetFile, setDatasetFile] = useState<{
    name: string;
    size: string;
    progress: number;
    uploaded: boolean;
  } | null>({
    name: 'TinyImageNet-Manifold-200k.tar.gz',
    size: '2.4 GB',
    progress: 100,
    uploaded: true,
  });

  const [codeFile, setCodeFile] = useState<{
    name: string;
    size: string;
    progress: number;
    uploaded: boolean;
  } | null>({
    name: 'diffusion_ddp_trainer.zip',
    size: '8.4 MB',
    progress: 100,
    uploaded: true,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  const steps: StepItem[] = [
    { id: 1, title: 'Project Info', subtitle: 'Architecture & Objectives' },
    { id: 2, title: 'Upload & Config', subtitle: 'Dataset & Training Code' },
    { id: 3, title: 'Review & Publish', subtitle: 'Put Online for Workers' },
  ];

  // Validation for Step 1
  const validateStep1 = () => {
    const errs: Record<string, string> = {};
    if (!formData.name.trim()) errs.name = 'Project name is required';
    if (!formData.description.trim()) errs.description = 'Description is required';
    if (!formData.trainingObjective.trim()) errs.trainingObjective = 'Training objective is required';
    if (!formData.datasetDescription.trim()) errs.datasetDescription = 'Dataset description is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // Validation for Step 2
  const validateStep2 = () => {
    const errs: Record<string, string> = {};
    if (!datasetFile) errs.dataset = 'Please select or upload a dataset package';
    if (!codeFile) errs.code = 'Please select or upload training model code';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (currentStep === 1) {
      if (validateStep1()) setCurrentStep(2);
    } else if (currentStep === 2) {
      if (validateStep2()) setCurrentStep(3);
    }
  };

  // Simulated File Upload Handling
  const handleDatasetUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setDatasetFile({
        name: file.name,
        size: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
        progress: 100,
        uploaded: true,
      });
      setFormData((prev) => ({ ...prev, datasetName: file.name }));
    }
  };

  const handleCodeUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setCodeFile({
        name: file.name,
        size: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
        progress: 100,
        uploaded: true,
      });
    }
  };

  // Pre-fill with diffusion model preset
  const applyDiffusionPreset = () => {
    setFormData({
      name: 'Diffusion Model from Scratch (Latent UNet)',
      description: 'Train a conditional 64x64 latent diffusion model for fast synthetic image generation using distributed gradient descent across volunteer nodes.',
      trainingObjective: 'Evaluate classifier-free guidance convergence on decentralized FP16 cluster.',
      modelArchitecture: 'Diffusion (UNet / DiT 180M)',
      datasetName: 'TinyImageNet-Manifold-200k',
      datasetDescription: '200,000 augmented images in 200 categories normalized to 64x64 FP16 tensors.',
      expectedDuration: '4 hours 15 mins',
      visibility: 'public',
      workersNeeded: 6,
      batchSize: 128,
      totalSteps: 10000,
      learningRate: '2e-4',
      optimizer: 'AdamW (beta1=0.9, beta2=0.999, weight_decay=0.01)',
      precision: 'fp16',
      checkpointInterval: 500,
      gradientAccumulationSteps: 2,
    });
    setDatasetFile({
      name: 'TinyImageNet-Manifold-200k.tar.gz',
      size: '2.4 GB',
      progress: 100,
      uploaded: true,
    });
    setCodeFile({
      name: 'diffusion_ddp_trainer.zip',
      size: '8.4 MB',
      progress: 100,
      uploaded: true,
    });
  };

  // Final Action: Put Project Online
  const handlePublishProject = () => {
    setIsPublishing(true);
    setTimeout(() => {
      const created = createProject({
        name: formData.name,
        description: formData.description,
        trainingObjective: formData.trainingObjective,
        modelArchitecture: formData.modelArchitecture,
        datasetName: formData.datasetName,
        datasetDescription: formData.datasetDescription,
        datasetSize: datasetFile ? datasetFile.size : '1.5 GB',
        codeFileName: codeFile ? codeFile.name : 'trainer.zip',
        codeFileSize: codeFile ? codeFile.size : '5 MB',
        expectedDuration: formData.expectedDuration,
        visibility: formData.visibility,
        workersNeeded: formData.workersNeeded,
        trainingStrategy: 'Distributed Data Parallel (DDP) with Mixed Precision',
        trainingConfig: {
          batchSize: formData.batchSize,
          totalSteps: formData.totalSteps,
          learningRate: formData.learningRate,
          optimizer: formData.optimizer,
          precision: formData.precision,
          checkpointInterval: formData.checkpointInterval,
          gradientAccumulationSteps: formData.gradientAccumulationSteps,
        },
      });

      setIsPublishing(false);
      setShowPublishModal(false);
      navigate(`/projects/${created.id}`);
    }, 600);
  };

  return (
    <div style={{ maxWidth: 880, margin: '0 auto' }} className="animate-fade-in">
      {/* Top Header */}
      <div style={{ marginBottom: 28, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 6 }}>
            Start New Project as Master
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Set up dataset packages, training workloads, and publish your project to volunteer workers.
          </p>
        </div>

        <button
          className="btn btn-secondary btn-sm"
          onClick={applyDiffusionPreset}
          style={{ borderColor: 'var(--accent-primary)' }}
        >
          <Sparkles size={14} color="var(--accent-primary)" />
          <span>Load Diffusion Demo Preset</span>
        </button>
      </div>

      {/* Stepper Navigation */}
      <Stepper
        steps={steps}
        currentStep={currentStep}
        onStepClick={(id) => setCurrentStep(id)}
      />

      {/* STEP 1: Project Information */}
      {currentStep === 1 && (
        <div className="card" style={{ padding: '28px 32px' }}>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: 18 }}>
            Step 1: Project Information
          </h3>

          <div className="form-group">
            <label className="form-label">
              <span>Project Name *</span>
              {errors.name && <span style={{ color: 'var(--status-stopped)', fontSize: '0.78rem' }}>{errors.name}</span>}
            </label>
            <input
              type="text"
              className="form-input"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Diffusion Model from Scratch"
            />
            <span className="form-hint">A clear, descriptive name for volunteer workers to identify your run.</span>
          </div>

          <div className="form-group">
            <label className="form-label">
              <span>Project Description *</span>
              {errors.description && <span style={{ color: 'var(--status-stopped)', fontSize: '0.78rem' }}>{errors.description}</span>}
            </label>
            <textarea
              className="form-textarea"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Describe the research goals, model scope, and expected results..."
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
            <div className="form-group">
              <label className="form-label">Model Architecture *</label>
              <select
                className="form-select"
                value={formData.modelArchitecture}
                onChange={(e) => setFormData({ ...formData, modelArchitecture: e.target.value })}
              >
                <option value="Diffusion (UNet / DiT 180M)">Diffusion (UNet / DiT 180M)</option>
                <option value="Transformer LLM (7B Adapter)">Transformer LLM (7B Adapter)</option>
                <option value="Vision Transformer (ViT-B/16)">Vision Transformer (ViT-B/16)</option>
                <option value="LoRA Fine-Tuning (Llama-3-8B)">LoRA Fine-Tuning (Llama-3-8B)</option>
                <option value="ResNet-50 Benchmark">ResNet-50 Distributed Benchmark</option>
              </select>
              <span className="form-hint">Architecture definition required for GPU memory validation.</span>
            </div>

            <div className="form-group">
              <label className="form-label">Workers Target Count</label>
              <input
                type="number"
                className="form-input"
                min={1}
                max={64}
                value={formData.workersNeeded}
                onChange={(e) => setFormData({ ...formData, workersNeeded: Number(e.target.value) })}
              />
              <span className="form-hint">Desired cluster size for distributed AllReduce.</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              <span>Training Objective *</span>
              {errors.trainingObjective && <span style={{ color: 'var(--status-stopped)', fontSize: '0.78rem' }}>{errors.trainingObjective}</span>}
            </label>
            <input
              type="text"
              className="form-input"
              value={formData.trainingObjective}
              onChange={(e) => setFormData({ ...formData, trainingObjective: e.target.value })}
              placeholder="e.g. Minimize FID score and cross-entropy loss on image manifold"
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              <span>Dataset Description *</span>
              {errors.datasetDescription && <span style={{ color: 'var(--status-stopped)', fontSize: '0.78rem' }}>{errors.datasetDescription}</span>}
            </label>
            <input
              type="text"
              className="form-input"
              value={formData.datasetDescription}
              onChange={(e) => setFormData({ ...formData, datasetDescription: e.target.value })}
              placeholder="e.g. 200,000 augmented images in 200 classes"
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
            <div className="form-group">
              <label className="form-label">Expected Duration</label>
              <input
                type="text"
                className="form-input"
                value={formData.expectedDuration}
                onChange={(e) => setFormData({ ...formData, expectedDuration: e.target.value })}
                placeholder="e.g. 4 hours 15 mins"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Visibility</label>
              <select
                className="form-select"
                value={formData.visibility}
                onChange={(e) => setFormData({ ...formData, visibility: e.target.value as 'public' | 'unlisted' })}
              >
                <option value="public">Public (Visible in Worker Discovery)</option>
                <option value="unlisted">Unlisted (Direct Invite Only)</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
            <button className="btn btn-primary btn-lg" onClick={handleNext}>
              <span>Next: Upload Dataset & Code</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: Upload Dataset & Model Training Code */}
      {currentStep === 2 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Explanation Alert */}
          <div className="alert-box alert-info">
            <Info size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <strong>Architecture Pipeline Requirements</strong>
              <p style={{ marginTop: 2, fontSize: '0.85rem' }}>
                The dataset contains the training examples distributed to volunteer worker caches.
                The model code defines the training workload, gradient computation, and loss objective.
              </p>
            </div>
          </div>

          {/* Dataset Upload Area */}
          <div className="card" style={{ padding: '24px 28px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <Database size={20} color="var(--accent-cyan)" />
              <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>
                1. Dataset Archive Upload
              </h3>
            </div>

            {datasetFile ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px 20px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div
                    style={{
                      padding: 10,
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--status-online-bg)',
                      color: 'var(--status-online)',
                    }}
                  >
                    <CheckCircle2 size={24} />
                  </div>
                  <div>
                    <strong style={{ fontSize: '0.95rem', display: 'block' }}>{datasetFile.name}</strong>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Size: {datasetFile.size} • Verified Format (Compressed Tensors)
                    </span>
                  </div>
                </div>

                <button
                  className="btn btn-danger-outline btn-sm"
                  onClick={() => setDatasetFile(null)}
                >
                  <Trash2 size={14} />
                  Remove
                </button>
              </div>
            ) : (
              <label
                style={{
                  border: '2px dashed var(--border-medium)',
                  borderRadius: 'var(--radius-lg)',
                  padding: '36px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  cursor: 'pointer',
                  backgroundColor: 'rgba(255, 255, 255, 0.01)',
                  transition: 'border-color var(--transition-fast)',
                }}
              >
                <UploadCloud size={36} color="var(--accent-primary)" />
                <div style={{ textAlign: 'center' }}>
                  <strong style={{ fontSize: '1rem', display: 'block' }}>
                    Drag & Drop Dataset Package or Click to Browse
                  </strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
                    Accepted: .zip, .tar.gz, .parquet, .h5, .npy (Max 10 GB demo allocation)
                  </span>
                </div>
                <input
                  type="file"
                  style={{ display: 'none' }}
                  onChange={handleDatasetUpload}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ pointerEvents: 'none', marginTop: 4 }}
                >
                  Browse Dataset File
                </button>
              </label>
            )}
            {errors.dataset && <span style={{ color: 'var(--status-stopped)', fontSize: '0.78rem', marginTop: 6, display: 'block' }}>{errors.dataset}</span>}
          </div>

          {/* Model Training Code Upload Area */}
          <div className="card" style={{ padding: '24px 28px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <FileCode size={20} color="var(--accent-primary)" />
              <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: 0 }}>
                2. Model Training Workload Code
              </h3>
            </div>

            {codeFile ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px 20px',
                  backgroundColor: 'var(--bg-input)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div
                    style={{
                      padding: 10,
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'var(--accent-primary-light)',
                      color: 'var(--accent-primary)',
                    }}
                  >
                    <CheckCircle2 size={24} />
                  </div>
                  <div>
                    <strong style={{ fontSize: '0.95rem', display: 'block' }}>{codeFile.name}</strong>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Size: {codeFile.size} • PyTorch Distributed Runtime Approved
                    </span>
                  </div>
                </div>

                <button
                  className="btn btn-danger-outline btn-sm"
                  onClick={() => setCodeFile(null)}
                >
                  <Trash2 size={14} />
                  Remove
                </button>
              </div>
            ) : (
              <label
                style={{
                  border: '2px dashed var(--border-medium)',
                  borderRadius: 'var(--radius-lg)',
                  padding: '36px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 12,
                  cursor: 'pointer',
                  backgroundColor: 'rgba(255, 255, 255, 0.01)',
                  transition: 'border-color var(--transition-fast)',
                }}
              >
                <UploadCloud size={36} color="var(--accent-primary)" />
                <div style={{ textAlign: 'center' }}>
                  <strong style={{ fontSize: '1rem', display: 'block' }}>
                    Select Training Script or Code Archive (ZIP)
                  </strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
                    Accepted: .zip, .tar.gz, .py (Includes train.py and requirements.txt)
                  </span>
                </div>
                <input
                  type="file"
                  style={{ display: 'none' }}
                  onChange={handleCodeUpload}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ pointerEvents: 'none', marginTop: 4 }}
                >
                  Browse Code Archive
                </button>
              </label>
            )}
            {errors.code && <span style={{ color: 'var(--status-stopped)', fontSize: '0.78rem', marginTop: 6, display: 'block' }}>{errors.code}</span>}
          </div>

          {/* Hyperparameter & Cluster Config */}
          <div className="card" style={{ padding: '24px 28px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: 16 }}>
              3. Distributed Training Hyperparameters
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Batch Size (Per Worker)</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.batchSize}
                  onChange={(e) => setFormData({ ...formData, batchSize: Number(e.target.value) })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Total Steps Target</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.totalSteps}
                  onChange={(e) => setFormData({ ...formData, totalSteps: Number(e.target.value) })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Learning Rate</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.learningRate}
                  onChange={(e) => setFormData({ ...formData, learningRate: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Precision</label>
                <select
                  className="form-select"
                  value={formData.precision}
                  onChange={(e) => setFormData({ ...formData, precision: e.target.value as any })}
                >
                  <option value="fp16">FP16 (Half Precision)</option>
                  <option value="bf16">BF16 (Brain Float)</option>
                  <option value="fp32">FP32 (Single Precision)</option>
                </select>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Optimizer</label>
              <input
                type="text"
                className="form-input"
                value={formData.optimizer}
                onChange={(e) => setFormData({ ...formData, optimizer: e.target.value })}
              />
            </div>
          </div>

          {/* Navigation Buttons */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
            <button className="btn btn-secondary" onClick={() => setCurrentStep(1)}>
              <ArrowLeft size={16} />
              <span>Back to Project Info</span>
            </button>

            <button className="btn btn-primary btn-lg" onClick={handleNext}>
              <span>Review & Put Online</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Review and Put Project Online */}
      {currentStep === 3 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div className="card" style={{ padding: '28px 32px' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 6 }}>
              Review Project Summary
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: 20 }}>
              Verify all architecture and dataset settings before broadcasting this job to volunteer nodes.
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 20,
                backgroundColor: 'var(--bg-input)',
                padding: '20px 24px',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-subtle)',
                marginBottom: 24,
              }}
            >
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Project Name</span>
                <strong style={{ display: 'block', fontSize: '1.1rem', marginTop: 2 }}>{formData.name}</strong>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Model Architecture</span>
                <strong style={{ display: 'block', fontSize: '1.05rem', color: 'var(--accent-primary)', marginTop: 2 }}>
                  {formData.modelArchitecture}
                </strong>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Dataset Archive</span>
                <span style={{ display: 'block', fontSize: '0.95rem', marginTop: 2 }}>
                  {datasetFile?.name} ({datasetFile?.size})
                </span>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Workload Code Archive</span>
                <span style={{ display: 'block', fontSize: '0.95rem', marginTop: 2 }}>
                  {codeFile?.name} ({codeFile?.size})
                </span>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Steps & Batch Size</span>
                <span className="mono" style={{ display: 'block', fontSize: '0.95rem', marginTop: 2 }}>
                  {formData.totalSteps.toLocaleString()} steps • Batch {formData.batchSize} • {formData.precision.toUpperCase()}
                </span>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Expected Duration</span>
                <span style={{ display: 'block', fontSize: '0.95rem', marginTop: 2 }}>
                  ~{formData.expectedDuration} ({formData.workersNeeded} nodes targeted)
                </span>
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
                Training Objective
              </span>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                {formData.trainingObjective}
              </p>
            </div>

            {/* Prototype notice */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '12px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(99, 102, 241, 0.08)',
                border: '1px solid var(--border-active)',
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                marginBottom: 24,
              }}
            >
              <AlertCircle size={18} color="var(--accent-primary)" style={{ flexShrink: 0 }} />
              <span>
                <strong>Frontend Prototype:</strong> Publishing simulates the project going online
                and adds it to the catalog. It will immediately open the shared training progress page.
              </span>
            </div>

            {/* Bottom Actions */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button className="btn btn-secondary" onClick={() => setCurrentStep(2)}>
                <ArrowLeft size={16} />
                <span>Back to Files</span>
              </button>

              <button
                className="btn btn-primary btn-lg"
                style={{ padding: '14px 32px' }}
                onClick={() => setShowPublishModal(true)}
              >
                <Sparkles size={18} />
                <span>Put Project Online</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      <Modal
        isOpen={showPublishModal}
        onClose={() => setShowPublishModal(false)}
        title="Put Project Online?"
        confirmLabel="Publish to Network"
        variant="primary"
        confirmLoading={isPublishing}
        onConfirm={handlePublishProject}
      >
        <p>
          You are about to publish <strong>{formData.name}</strong> to the peer-to-peer compute network.
        </p>
        <ul style={{ marginTop: 12, paddingLeft: 20, fontSize: '0.88rem', lineHeight: 1.6 }}>
          <li>Makes the demo project discoverable in the Worker Discovery catalog.</li>
          <li>Assigns you as the <strong>Master</strong> coordinator.</li>
          <li>Initializes the simulated gradient distribution cluster.</li>
        </ul>
      </Modal>
    </div>
  );
};
