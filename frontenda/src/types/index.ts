export type UserRole = 'none' | 'master' | 'worker' | 'master_and_worker';

export type ProjectStatus = 
  | 'online' 
  | 'training' 
  | 'paused' 
  | 'stopped' 
  | 'completed' 
  | 'looking_for_workers';

export type WorkerStatus = 'training' | 'idle' | 'paused' | 'offline';

export type ContributionStatus = 'active' | 'paused' | 'offline';

export interface UserProfile {
  id: string;
  username: string;
  displayName: string;
  email: string;
  avatar: string;
}

export interface TrainingConfig {
  batchSize: number;
  totalSteps: number;
  learningRate: string;
  optimizer: string;
  precision: 'fp16' | 'bf16' | 'fp32';
  checkpointInterval: number;
  gradientAccumulationSteps?: number;
}

export interface MetricHistoryPoint {
  step: number;
  loss: number;
  speed: number; // steps/sec
  clusterCpuUtil: number; // percent
  clusterGpuUtil: number; // percent
  ramUtilGB: number;
  timestamp: string;
}

export interface TrainingMetrics {
  currentStep: number;
  totalSteps: number;
  progressPercent: number;
  currentLoss: number;
  trainingSpeed: number; // steps/sec
  elapsedTimeSeconds: number;
  estimatedRemainingSeconds: number;
  history: MetricHistoryPoint[];
}

export interface WorkerNode {
  id: string;
  name: string;
  isCurrentUser: boolean;
  status: WorkerStatus;
  cpuModel: string;
  cpuCoresTotal: number;
  cpuCoresContributed: number;
  ramTotalGB: number;
  ramContributedGB: number;
  gpuModel: string;
  gpuMemoryTotalGB: number;
  gpuEnabled: boolean;
  currentBatch: number;
  stepsProcessed: number;
  lastHeartbeat: string;
  storageBudgetGB: number;
  networkBandwidthMbps: number;
  contributionStatus: ContributionStatus;
}

export interface TrainingEvent {
  id: string;
  timestamp: string;
  type: 'system' | 'worker' | 'training' | 'checkpoint' | 'alert';
  message: string;
  workerName?: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  trainingObjective: string;
  modelArchitecture: string;
  datasetName: string;
  datasetDescription: string;
  datasetSize: string;
  codeFileName: string;
  codeFileSize: string;
  status: ProjectStatus;
  owner: {
    id: string;
    name: string;
    isCurrentUser: boolean;
  };
  createdAt: string;
  expectedDuration: string;
  visibility: 'public' | 'unlisted';
  trainingStrategy: string;
  trainingConfig: TrainingConfig;
  metrics: TrainingMetrics;
  workers: WorkerNode[];
  workersNeeded: number;
  logs: TrainingEvent[];
  requirements: {
    minCpuCores: number;
    minRamGB: number;
    gpuRecommended: boolean;
    minVramGB?: number;
  };
}

export interface HardwareProfile {
  cpuModel: string;
  cpuCores: number;
  ramTotalGB: number;
  ramAvailableGB: number;
  gpuModel: string;
  gpuMemoryTotalGB: number;
  diskSpaceAvailableGB: number;
}

export interface ContributionSettings {
  cpuEnabled: boolean;
  cpuCores: number;
  ramBudgetGB: number;
  gpuEnabled: boolean;
  selectedGpu: string;
  storageBudgetGB: number;
  networkPreference: 'unlimited' | 'moderate' | 'saver';
  globalPaused: boolean;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  type: 'info' | 'success' | 'warning' | 'alert';
  projectId?: string;
}

export interface AppSettings {
  theme: 'dark' | 'light' | 'system';
  accentColor: 'violet' | 'blue' | 'cyan' | 'emerald';
  notifications: {
    workerJoined: boolean;
    projectStatusChanged: boolean;
    trainingCompleted: boolean;
    trainingFailed: boolean;
    resourceWarning: boolean;
  };
  appPreferences: {
    defaultDashboard: 'overview' | 'projects';
    confirmDestructiveActions: boolean;
    enableLiveUpdates: boolean;
    simulationSpeed: number; // 1, 2, 5
  };
  userProfile: UserProfile;
}
