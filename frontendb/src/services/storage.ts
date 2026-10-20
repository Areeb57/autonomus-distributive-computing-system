import type {
  Role,
  MasterProject,
  WorkerProject,
  GlobalResourceSettings,
  UserSettings,
  HardwareSpecs,
  ConnectedWorker
} from '../types';
import { generateProjectCode } from '../utils/formatting';

export const HARDWARE_SPECS: HardwareSpecs = {
  cpuModel: 'AMD Ryzen 9 7950X (16 Cores / 32 Threads)',
  cpuTotalCores: 16,
  cpuAvailableCores: 14,
  ramTotalGb: 64,
  ramAvailableGb: 48,
  gpuModel: 'NVIDIA GeForce RTX 4090 (24 GB GDDR6X)',
  gpuVramGb: 24,
  storageTotalGb: 1024,
  storageAvailableGb: 520
};

export const MOCK_WORKERS: ConnectedWorker[] = [
  {
    id: 'w-1092',
    name: 'worker-us-east-01',
    status: 'computing',
    cpuCores: 16,
    allocatedCpuCores: 12,
    ramGb: 64,
    allocatedRamGb: 48,
    gpuName: 'RTX 4090 24GB',
    allocatedGpuPercent: 85,
    latencyMs: 24,
    currentBatch: 'Batch 1,420 (Loss: 0.321)'
  },
  {
    id: 'w-3841',
    name: 'worker-eu-west-04',
    status: 'computing',
    cpuCores: 32,
    allocatedCpuCores: 24,
    ramGb: 128,
    allocatedRamGb: 96,
    gpuName: 'A100 SXM 80GB',
    allocatedGpuPercent: 95,
    latencyMs: 42,
    currentBatch: 'Batch 1,421 (Loss: 0.318)'
  },
  {
    id: 'w-9024',
    name: 'worker-ap-east-02',
    status: 'active',
    cpuCores: 8,
    allocatedCpuCores: 6,
    ramGb: 32,
    allocatedRamGb: 24,
    gpuName: 'RTX 3090 24GB',
    allocatedGpuPercent: 70,
    latencyMs: 68,
    currentBatch: 'Batch 1,422 (Loss: 0.325)'
  }
];

export const DEFAULT_USER_SETTINGS: UserSettings = {
  username: 'researcher_demo',
  email: 'researcher@adc-network.io',
  theme: 'light',
  notifyMilestones: true,
  notifyWorkerDisconnect: true,
  notifyThermalThrottle: false,
  autoThrottleBattery: true,
  allowBackgroundTraining: true
};

export const DEFAULT_RESOURCE_SETTINGS: GlobalResourceSettings = {
  globalPaused: false,
  cpuBudgetPercent: 80,
  cpuCoresToContribute: 4,
  ramBudgetGb: 32,
  gpuBudgetPercent: 85,
  gpuVramLimitGb: 8,
  storageBudgetGb: 150
};

const STORAGE_KEYS = {
  ROLE: 'adc_role',
  MASTER_PROJECT: 'adc_master_project',
  WORKER_PROJECT: 'adc_worker_project',
  RESOURCE_SETTINGS: 'adc_resource_settings',
  USER_SETTINGS: 'adc_user_settings'
};

export const storageService = {
  getRole(): Role {
    const role = localStorage.getItem(STORAGE_KEYS.ROLE);
    if (role === 'master' || role === 'worker') return role;
    return 'none';
  },

  setRole(role: Role): void {
    localStorage.setItem(STORAGE_KEYS.ROLE, role);
  },

  getMasterProject(): MasterProject | null {
    const data = localStorage.getItem(STORAGE_KEYS.MASTER_PROJECT);
    if (!data) return null;
    try {
      return JSON.parse(data) as MasterProject;
    } catch {
      return null;
    }
  },

  setMasterProject(project: MasterProject | null): void {
    if (!project) {
      localStorage.removeItem(STORAGE_KEYS.MASTER_PROJECT);
    } else {
      localStorage.setItem(STORAGE_KEYS.MASTER_PROJECT, JSON.stringify(project));
    }
  },

  getWorkerProject(): WorkerProject | null {
    const data = localStorage.getItem(STORAGE_KEYS.WORKER_PROJECT);
    if (!data) return null;
    try {
      return JSON.parse(data) as WorkerProject;
    } catch {
      return null;
    }
  },

  setWorkerProject(project: WorkerProject | null): void {
    if (!project) {
      localStorage.removeItem(STORAGE_KEYS.WORKER_PROJECT);
    } else {
      localStorage.setItem(STORAGE_KEYS.WORKER_PROJECT, JSON.stringify(project));
    }
  },

  getResourceSettings(): GlobalResourceSettings {
    const data = localStorage.getItem(STORAGE_KEYS.RESOURCE_SETTINGS);
    if (!data) return DEFAULT_RESOURCE_SETTINGS;
    try {
      return { ...DEFAULT_RESOURCE_SETTINGS, ...JSON.parse(data) };
    } catch {
      return DEFAULT_RESOURCE_SETTINGS;
    }
  },

  setResourceSettings(settings: GlobalResourceSettings): void {
    localStorage.setItem(STORAGE_KEYS.RESOURCE_SETTINGS, JSON.stringify(settings));
  },

  getUserSettings(): UserSettings {
    const data = localStorage.getItem(STORAGE_KEYS.USER_SETTINGS);
    if (!data) return DEFAULT_USER_SETTINGS;
    try {
      return { ...DEFAULT_USER_SETTINGS, ...JSON.parse(data) };
    } catch {
      return DEFAULT_USER_SETTINGS;
    }
  },

  setUserSettings(settings: UserSettings): void {
    localStorage.setItem(STORAGE_KEYS.USER_SETTINGS, JSON.stringify(settings));
  },

  /**
   * Reset all demo state to fresh default (no agent connected)
   */
  resetDemo(): void {
    localStorage.removeItem(STORAGE_KEYS.ROLE);
    localStorage.removeItem(STORAGE_KEYS.MASTER_PROJECT);
    localStorage.removeItem(STORAGE_KEYS.WORKER_PROJECT);
    localStorage.removeItem(STORAGE_KEYS.RESOURCE_SETTINGS);
    // Keep user theme if set, reset rest
    const currentSettings = this.getUserSettings();
    this.setUserSettings({
      ...DEFAULT_USER_SETTINGS,
      theme: currentSettings.theme || 'light'
    });
  },

  /**
   * Pre-seed a sample Master project online for quick testing if needed
   */
  seedSampleMasterProject(): MasterProject {
    const code = generateProjectCode();
    const sample: MasterProject = {
      id: 'proj-' + Date.now(),
      name: 'Llama-3-8B Fine-tuning (Medical QA)',
      description: 'Distributed LoRA fine-tuning across ADC cluster nodes.',
      datasetFileName: 'pubmed_qa_instruct_v2.parquet',
      datasetFileSize: '1.4 GB',
      codeFileName: 'train_lora_ddp.py',
      codeFileSize: '48.2 KB',
      projectCode: code,
      status: 'training',
      progress: 38.4,
      currentStep: 1536,
      totalSteps: 4000,
      loss: 0.3421,
      speed: '164 samples/s',
      elapsedSeconds: 4210,
      estimatedRemainingSeconds: 6750,
      createdAt: new Date().toISOString(),
      workers: [...MOCK_WORKERS]
    };
    this.setMasterProject(sample);
    return sample;
  }
};
