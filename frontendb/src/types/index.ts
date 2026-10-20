export type Role = 'none' | 'master' | 'worker';

export type ProjectStatus = 'draft' | 'online' | 'training' | 'paused' | 'stopped' | 'ended';

export type WorkerContributionStatus = 'idle' | 'active' | 'computing' | 'paused' | 'stopped';

export interface ConnectedWorker {
  id: string;
  name: string;
  status: 'computing' | 'active' | 'idle' | 'paused';
  cpuCores: number;
  allocatedCpuCores: number;
  ramGb: number;
  allocatedRamGb: number;
  gpuName: string;
  allocatedGpuPercent: number;
  latencyMs: number;
  currentBatch: string;
}

export interface MasterProject {
  id: string;
  name: string;
  description: string;
  datasetFileName: string;
  datasetFileSize: string;
  codeFileName: string;
  codeFileSize: string;
  projectCode: string; // 9 numeric digits
  status: ProjectStatus;
  progress: number; // 0 - 100
  currentStep: number;
  totalSteps: number;
  loss: number;
  speed: string; // e.g. "164 samples/s"
  elapsedSeconds: number;
  estimatedRemainingSeconds: number;
  createdAt: string;
  workers: ConnectedWorker[];
}

export interface HardwareSpecs {
  cpuModel: string;
  cpuTotalCores: number;
  cpuAvailableCores: number;
  ramTotalGb: number;
  ramAvailableGb: number;
  gpuModel: string;
  gpuVramGb: number;
  storageTotalGb: number;
  storageAvailableGb: number;
}

export interface WorkerAllocation {
  cpuPercent: number;
  allocatedCpuCores: number;
  ramGb: number;
  gpuPercent: number;
  allocatedVramGb: number;
  storageGb: number;
}

export interface WorkerProject {
  projectCode: string;
  projectName: string;
  allocation: WorkerAllocation;
  status: WorkerContributionStatus;
  assignedTask: string;
  currentProgress: number;
  currentStep: number;
  totalSteps: number;
  cpuUsage: number; // percentage (live simulated)
  ramUsageGb: number;
  gpuUsage: number; // percentage
  joinedAt: string;
}

export interface GlobalResourceSettings {
  globalPaused: boolean;
  cpuBudgetPercent: number;
  cpuCoresToContribute: number;
  ramBudgetGb: number;
  gpuBudgetPercent: number;
  gpuVramLimitGb: number;
  storageBudgetGb: number;
}

export interface UserSettings {
  username: string;
  email: string;
  theme: 'light' | 'dark';
  notifyMilestones: boolean;
  notifyWorkerDisconnect: boolean;
  notifyThermalThrottle: boolean;
  autoThrottleBattery: boolean;
  allowBackgroundTraining: boolean;
}
