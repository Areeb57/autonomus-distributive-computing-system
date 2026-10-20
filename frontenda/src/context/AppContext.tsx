import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import type {
  Project,
  UserRole,
  UserProfile,
  HardwareProfile,
  ContributionSettings,
  AppSettings,
  NotificationItem,
  WorkerNode,
  TrainingEvent,
  MetricHistoryPoint,
} from '../types';
import { mockDefaultProjects } from '../data/mockProjects';
import { mockDefaultHardware, defaultContributionSettings } from '../data/mockHardware';

const LOCAL_STORAGE_KEYS = {
  PROJECTS: 'adc_ai_projects_v2',
  ACTIVE_PROJECT_ID: 'adc_ai_active_project_id_v2',
  USER_ROLE: 'adc_ai_user_role_v2',
  USER_PROFILE: 'adc_ai_user_profile_v2',
  HARDWARE: 'adc_ai_hardware_v2',
  CONTRIBUTION: 'adc_ai_contribution_v2',
  SETTINGS: 'adc_ai_settings_v2',
  NOTIFICATIONS: 'adc_ai_notifications_v2',
};

const defaultUserProfile: UserProfile = {
  id: 'usr-current-volunteer',
  username: 'antigravity_dev',
  displayName: 'Alex Mercer (You)',
  email: 'alex.mercer@distributed-ai.local',
  avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&q=80',
};

const defaultAppSettings: AppSettings = {
  theme: 'dark',
  accentColor: 'violet',
  notifications: {
    workerJoined: true,
    projectStatusChanged: true,
    trainingCompleted: true,
    trainingFailed: true,
    resourceWarning: true,
  },
  appPreferences: {
    defaultDashboard: 'overview',
    confirmDestructiveActions: true,
    enableLiveUpdates: true,
    simulationSpeed: 1,
  },
  userProfile: defaultUserProfile,
};

const initialNotifications: NotificationItem[] = [
  {
    id: 'notif-1',
    title: 'Cluster Status Normal',
    message: 'Decentralized P2P node mesh initialized. Ready for training tasks.',
    timestamp: '10m ago',
    read: false,
    type: 'info',
  },
  {
    id: 'notif-2',
    title: 'New High-Priority Job',
    message: 'Diffusion Model from Scratch is requesting volunteer GPU nodes.',
    timestamp: '25m ago',
    read: false,
    type: 'success',
    projectId: 'proj-diffusion-scratch',
  },
];

interface AppContextType {
  projects: Project[];
  activeProjectId: string | null;
  activeProject: Project | null;
  currentUserRole: UserRole;
  userProfile: UserProfile;
  hardwareProfile: HardwareProfile;
  contributionSettings: ContributionSettings;
  appSettings: AppSettings;
  notifications: NotificationItem[];
  unreadNotificationCount: number;
  
  // Actions
  setActiveProjectId: (id: string | null) => void;
  setUserRole: (role: UserRole) => void;
  createProject: (newProjectData: Partial<Project>) => Project;
  joinProjectAsWorker: (projectId: string, contribution: ContributionSettings) => void;
  pauseWorkerContribution: (projectId: string) => void;
  resumeWorkerContribution: (projectId: string) => void;
  stopWorkerContribution: (projectId: string) => void;
  pauseProjectTraining: (projectId: string) => void;
  resumeProjectTraining: (projectId: string) => void;
  stopProjectTraining: (projectId: string) => void;
  stopProjectAsMaster: (projectId: string) => void;
  updateContributionSettings: (settings: ContributionSettings) => void;
  updateUserProfile: (profile: Partial<UserProfile>) => void;
  updateAppSettings: (settings: Partial<AppSettings>) => void;
  setTheme: (theme: 'dark' | 'light' | 'system') => void;
  markNotificationRead: (id: string) => void;
  markAllNotificationsRead: () => void;
  clearAllNotifications: () => void;
  addNotification: (title: string, message: string, type?: NotificationItem['type'], projectId?: string) => void;
  resetDemoData: () => void;
  getProjectById: (id: string) => Project | undefined;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Load state from localStorage or defaults
  const [projects, setProjects] = useState<Project[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.PROJECTS);
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed to parse saved projects', e);
    }
    return mockDefaultProjects;
  });

  const [activeProjectId, setActiveProjectId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(LOCAL_STORAGE_KEYS.ACTIVE_PROJECT_ID) || null;
    } catch {
      return null;
    }
  });

  const [currentUserRole, setCurrentUserRole] = useState<UserRole>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.USER_ROLE);
      if (saved) return saved as UserRole;
    } catch {
      // fallback
    }
    return 'none';
  });

  const [userProfile, setUserProfileState] = useState<UserProfile>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.USER_PROFILE);
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return defaultUserProfile;
  });

  const [hardwareProfile] = useState<HardwareProfile>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.HARDWARE);
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return mockDefaultHardware;
  });

  const [contributionSettings, setContributionSettings] = useState<ContributionSettings>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.CONTRIBUTION);
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return defaultContributionSettings;
  });

  const [appSettings, setAppSettingsState] = useState<AppSettings>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.SETTINGS);
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return defaultAppSettings;
  });

  const [notifications, setNotifications] = useState<NotificationItem[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEYS.NOTIFICATIONS);
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return initialNotifications;
  });

  // Sync state changes to localStorage
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.PROJECTS, JSON.stringify(projects));
  }, [projects]);

  useEffect(() => {
    if (activeProjectId) {
      localStorage.setItem(LOCAL_STORAGE_KEYS.ACTIVE_PROJECT_ID, activeProjectId);
    } else {
      localStorage.removeItem(LOCAL_STORAGE_KEYS.ACTIVE_PROJECT_ID);
    }
  }, [activeProjectId]);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.USER_ROLE, currentUserRole);
  }, [currentUserRole]);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.USER_PROFILE, JSON.stringify(userProfile));
  }, [userProfile]);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.CONTRIBUTION, JSON.stringify(contributionSettings));
  }, [contributionSettings]);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.SETTINGS, JSON.stringify(appSettings));
  }, [appSettings]);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEYS.NOTIFICATIONS, JSON.stringify(notifications));
  }, [notifications]);

  // Handle Theme switching in document.documentElement
  useEffect(() => {
    const root = document.documentElement;
    const theme = appSettings.theme;
    if (theme === 'system') {
      const isSystemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.setAttribute('data-theme', isSystemDark ? 'dark' : 'light');
    } else {
      root.setAttribute('data-theme', theme);
    }
  }, [appSettings.theme]);

  // Helper notification adder
  const addNotification = useCallback((
    title: string,
    message: string,
    type: NotificationItem['type'] = 'info',
    projectId?: string
  ) => {
    const newNotif: NotificationItem = {
      id: `notif-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      title,
      message,
      timestamp: 'Just now',
      read: false,
      type,
      projectId,
    };
    setNotifications((prev) => [newNotif, ...prev.slice(0, 19)]);
  }, []);

  // Compute active project
  const activeProject = useMemo(() => {
    if (!activeProjectId) return null;
    return projects.find((p) => p.id === activeProjectId) || null;
  }, [projects, activeProjectId]);

  const getProjectById = useCallback((id: string) => {
    return projects.find((p) => p.id === id);
  }, [projects]);

  // Master: Create Project
  const createProject = useCallback((newProjectData: Partial<Project>): Project => {
    const projectId = `proj-${Date.now().toString(36)}`;
    const fullProject: Project = {
      id: projectId,
      name: newProjectData.name || 'Untitled Distributed AI Job',
      description: newProjectData.description || 'Distributed training project coordinated across volunteer nodes.',
      trainingObjective: newProjectData.trainingObjective || 'Train neural network model collaboratively.',
      modelArchitecture: newProjectData.modelArchitecture || 'Diffusion (UNet / DiT 180M)',
      datasetName: newProjectData.datasetName || 'Uploaded Dataset Archive',
      datasetDescription: newProjectData.datasetDescription || 'User-provided dataset package.',
      datasetSize: newProjectData.datasetSize || '500 MB',
      codeFileName: newProjectData.codeFileName || 'trainer.zip',
      codeFileSize: newProjectData.codeFileSize || '2.5 MB',
      status: 'online',
      owner: {
        id: userProfile.id,
        name: userProfile.displayName,
        isCurrentUser: true,
      },
      createdAt: new Date().toISOString(),
      expectedDuration: newProjectData.expectedDuration || '3 hours 45 mins',
      visibility: newProjectData.visibility || 'public',
      trainingStrategy: newProjectData.trainingStrategy || 'Distributed Data Parallel (DDP)',
      trainingConfig: newProjectData.trainingConfig || {
        batchSize: 64,
        totalSteps: 8000,
        learningRate: '2e-4',
        optimizer: 'AdamW',
        precision: 'fp16',
        checkpointInterval: 500,
        gradientAccumulationSteps: 2,
      },
      metrics: {
        currentStep: 0,
        totalSteps: newProjectData.trainingConfig?.totalSteps || 8000,
        progressPercent: 0,
        currentLoss: 0.95,
        trainingSpeed: 8.5,
        elapsedTimeSeconds: 0,
        estimatedRemainingSeconds: 13500,
        history: [
          {
            step: 0,
            loss: 0.95,
            speed: 8.5,
            clusterCpuUtil: 65,
            clusterGpuUtil: 85,
            ramUtilGB: 18.2,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ],
      },
      workers: [],
      workersNeeded: newProjectData.workersNeeded || 6,
      requirements: newProjectData.requirements || {
        minCpuCores: 4,
        minRamGB: 8,
        gpuRecommended: true,
        minVramGB: 8,
      },
      logs: [
        {
          id: `log-${Date.now()}-1`,
          timestamp: new Date().toLocaleTimeString(),
          type: 'system',
          message: `Project "${newProjectData.name}" published online by Master ${userProfile.displayName}. Waiting for worker nodes.`,
        },
      ],
    };

    setProjects((prev) => [fullProject, ...prev]);
    setActiveProjectId(projectId);
    setCurrentUserRole((prevRole) => (prevRole === 'worker' ? 'master_and_worker' : 'master'));
    addNotification('Project Created & Published', `Project "${fullProject.name}" is now online!`, 'success', projectId);

    return fullProject;
  }, [userProfile, addNotification]);

  // Worker: Join Project
  const joinProjectAsWorker = useCallback((projectId: string, contribution: ContributionSettings) => {
    const userWorkerNode: WorkerNode = {
      id: `worker-current-user-${Date.now().toString(36)}`,
      name: `${userProfile.displayName} (You)`,
      isCurrentUser: true,
      status: 'training',
      cpuModel: hardwareProfile.cpuModel,
      cpuCoresTotal: hardwareProfile.cpuCores,
      cpuCoresContributed: contribution.cpuEnabled ? contribution.cpuCores : 0,
      ramTotalGB: hardwareProfile.ramTotalGB,
      ramContributedGB: contribution.ramBudgetGB,
      gpuModel: contribution.gpuEnabled ? contribution.selectedGpu : 'CPU-only mode',
      gpuMemoryTotalGB: contribution.gpuEnabled ? hardwareProfile.gpuMemoryTotalGB : 0,
      gpuEnabled: contribution.gpuEnabled,
      currentBatch: 64,
      stepsProcessed: 0,
      lastHeartbeat: 'Just now',
      storageBudgetGB: contribution.storageBudgetGB,
      networkBandwidthMbps: contribution.networkPreference === 'unlimited' ? 300 : contribution.networkPreference === 'moderate' ? 150 : 50,
      contributionStatus: 'active',
    };

    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          // Check if already in workers
          const filteredWorkers = p.workers.filter((w) => !w.isCurrentUser);
          const newStatus = p.status === 'online' || p.status === 'looking_for_workers' ? 'training' : p.status;
          const newEvent: TrainingEvent = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            type: 'worker',
            message: `${userProfile.displayName} joined as a volunteer worker with ${contribution.cpuCores} cores, ${contribution.ramBudgetGB}GB RAM${contribution.gpuEnabled ? ` and ${contribution.selectedGpu}` : ''}.`,
            workerName: userProfile.displayName,
          };
          return {
            ...p,
            status: newStatus,
            workers: [...filteredWorkers, userWorkerNode],
            logs: [newEvent, ...p.logs],
          };
        }
        return p;
      })
    );

    setActiveProjectId(projectId);
    setCurrentUserRole((prevRole) => (prevRole === 'master' ? 'master_and_worker' : 'worker'));
    addNotification('Joined Project as Worker', `You are now contributing compute to project: ${projectId}`, 'success', projectId);
  }, [userProfile, hardwareProfile, addNotification]);

  // Worker: Pause contribution
  const pauseWorkerContribution = useCallback((projectId: string) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          const updatedWorkers = p.workers.map((w) => {
            if (w.isCurrentUser) {
              return {
                ...w,
                status: 'paused' as const,
                contributionStatus: 'paused' as const,
                lastHeartbeat: 'Paused by user',
              };
            }
            return w;
          });
          const newEvent: TrainingEvent = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            type: 'worker',
            message: `${userProfile.displayName} paused local hardware contribution. Cluster continues with remaining nodes.`,
            workerName: userProfile.displayName,
          };
          return {
            ...p,
            workers: updatedWorkers,
            logs: [newEvent, ...p.logs],
          };
        }
        return p;
      })
    );
    addNotification('Contribution Paused', 'Your local node contribution is paused.', 'warning', projectId);
  }, [userProfile, addNotification]);

  // Worker: Resume contribution
  const resumeWorkerContribution = useCallback((projectId: string) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          const updatedWorkers = p.workers.map((w) => {
            if (w.isCurrentUser) {
              return {
                ...w,
                status: 'training' as const,
                contributionStatus: 'active' as const,
                lastHeartbeat: 'Just now',
              };
            }
            return w;
          });
          const newEvent: TrainingEvent = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            type: 'worker',
            message: `${userProfile.displayName} resumed hardware contribution to distributed training pool.`,
            workerName: userProfile.displayName,
          };
          return {
            ...p,
            workers: updatedWorkers,
            logs: [newEvent, ...p.logs],
          };
        }
        return p;
      })
    );
    addNotification('Contribution Resumed', 'Your local compute contribution is active again.', 'success', projectId);
  }, [userProfile, addNotification]);

  // Worker: Stop Contributing
  const stopWorkerContribution = useCallback((projectId: string) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          const updatedWorkers = p.workers.filter((w) => !w.isCurrentUser);
          const newEvent: TrainingEvent = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            type: 'worker',
            message: `${userProfile.displayName} disconnected and withdrew computing resources.`,
            workerName: userProfile.displayName,
          };
          return {
            ...p,
            workers: updatedWorkers,
            logs: [newEvent, ...p.logs],
          };
        }
        return p;
      })
    );

    // Update role
    setCurrentUserRole((prevRole) => {
      if (prevRole === 'master_and_worker') return 'master';
      return 'none';
    });

    if (activeProjectId === projectId) {
      // If user was only worker on this project, clear activeProjectId
      if (currentUserRole !== 'master' && currentUserRole !== 'master_and_worker') {
        setActiveProjectId(null);
      }
    }

    addNotification('Stopped Contribution', 'You disconnected from the project compute cluster.', 'info');
  }, [userProfile, activeProjectId, currentUserRole, addNotification]);

  // Master: Pause Training (Project-level)
  const pauseProjectTraining = useCallback((projectId: string) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          const newEvent: TrainingEvent = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            type: 'training',
            message: 'Master paused project training. Gradient descent & step advancement halted for all nodes.',
          };
          return {
            ...p,
            status: 'paused' as const,
            logs: [newEvent, ...p.logs],
          };
        }
        return p;
      })
    );
    addNotification('Training Paused', 'Training simulation has been paused across the cluster.', 'warning', projectId);
  }, [addNotification]);

  // Master: Resume Training (Project-level)
  const resumeProjectTraining = useCallback((projectId: string) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          const newEvent: TrainingEvent = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            type: 'training',
            message: 'Master resumed project training. Cluster synchronization resumed.',
          };
          return {
            ...p,
            status: 'training' as const,
            logs: [newEvent, ...p.logs],
          };
        }
        return p;
      })
    );
    addNotification('Training Resumed', 'Cluster training resumed.', 'success', projectId);
  }, [addNotification]);

  // Master: Stop Training (Project-level)
  const stopProjectTraining = useCallback((projectId: string) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          const newEvent: TrainingEvent = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString(),
            type: 'training',
            message: 'Training job stopped by Master. Model weights saved to checkpoint directory.',
          };
          return {
            ...p,
            status: 'stopped' as const,
            logs: [newEvent, ...p.logs],
          };
        }
        return p;
      })
    );
    addNotification('Training Stopped', 'Training job has been stopped.', 'alert', projectId);
  }, [addNotification]);

  // Master: Stop Project (Remove Master ownership/role)
  const stopProjectAsMaster = useCallback((projectId: string) => {
    setProjects((prev) =>
      prev.map((p) => {
        if (p.id === projectId) {
          return {
            ...p,
            status: 'stopped' as const,
            owner: {
              ...p.owner,
              isCurrentUser: false,
            },
          };
        }
        return p;
      })
    );

    setCurrentUserRole((prevRole) => {
      if (prevRole === 'master_and_worker') return 'worker';
      return 'none';
    });

    if (activeProjectId === projectId) {
      if (currentUserRole !== 'worker' && currentUserRole !== 'master_and_worker') {
        setActiveProjectId(null);
      }
    }

    addNotification('Project Ended', 'You have closed and ended management for this project.', 'info');
  }, [activeProjectId, currentUserRole, addNotification]);

  // Settings
  const updateContributionSettings = useCallback((settings: ContributionSettings) => {
    setContributionSettings(settings);
    // Also update current user worker node in projects if joined
    setProjects((prev) =>
      prev.map((p) => {
        const hasUserWorker = p.workers.some((w) => w.isCurrentUser);
        if (!hasUserWorker) return p;
        return {
          ...p,
          workers: p.workers.map((w) => {
            if (w.isCurrentUser) {
              return {
                ...w,
                cpuCoresContributed: settings.cpuEnabled ? settings.cpuCores : 0,
                ramContributedGB: settings.ramBudgetGB,
                gpuModel: settings.gpuEnabled ? settings.selectedGpu : 'CPU-only mode',
                gpuEnabled: settings.gpuEnabled,
                storageBudgetGB: settings.storageBudgetGB,
              };
            }
            return w;
          }),
        };
      })
    );
    addNotification('Resource Budget Updated', 'Your computing contribution settings were saved.', 'success');
  }, [addNotification]);

  const updateUserProfile = useCallback((profile: Partial<UserProfile>) => {
    setUserProfileState((prev) => ({ ...prev, ...profile }));
  }, []);

  const updateAppSettings = useCallback((settings: Partial<AppSettings>) => {
    setAppSettingsState((prev) => ({ ...prev, ...settings }));
  }, []);

  const setTheme = useCallback((theme: 'dark' | 'light' | 'system') => {
    setAppSettingsState((prev) => ({ ...prev, theme }));
  }, []);

  const markNotificationRead = useCallback((id: string) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
  }, []);

  const markAllNotificationsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  // Reset all state to defaults
  const resetDemoData = useCallback(() => {
    localStorage.clear();
    setProjects(mockDefaultProjects);
    setActiveProjectId(null);
    setCurrentUserRole('none');
    setUserProfileState(defaultUserProfile);
    setContributionSettings(defaultContributionSettings);
    setAppSettingsState(defaultAppSettings);
    setNotifications(initialNotifications);
    addNotification('Demo Data Reset', 'All projects, roles, and settings restored to clean demo state.', 'info');
  }, [addNotification]);

  // LIVE TRAINING SIMULATOR
  useEffect(() => {
    if (!appSettings.appPreferences.enableLiveUpdates) return;

    const intervalMs = Math.round(3000 / appSettings.appPreferences.simulationSpeed);

    const timer = setInterval(() => {
      setProjects((currentProjects) => {
        let hasChanges = false;

        const updated = currentProjects.map((project) => {
          // Simulator only steps forward if status is 'training'
          if (project.status !== 'training') return project;

          // Check if at least one worker is actively training
          const activeWorkers = project.workers.filter(
            (w) => w.status === 'training' && w.contributionStatus === 'active'
          );

          if (activeWorkers.length === 0) return project;

          hasChanges = true;

          const stepIncrement = Math.max(1, Math.round(project.metrics.trainingSpeed * 2.8));
          const newStep = Math.min(project.metrics.totalSteps, project.metrics.currentStep + stepIncrement);
          const newPercent = Math.min(100, Math.round((newStep / project.metrics.totalSteps) * 100));
          const isFinished = newStep >= project.metrics.totalSteps;

          // Gradual loss decay with natural mini-fluctuation
          const lossDecay = 0.9985;
          const noise = (Math.random() * 0.0008) - 0.0004;
          const newLoss = Math.max(0.015, Number((project.metrics.currentLoss * lossDecay + noise).toFixed(4)));

          const newElapsed = project.metrics.elapsedTimeSeconds + 3;
          const remainingSteps = project.metrics.totalSteps - newStep;
          const estimatedRemaining = Math.max(0, Math.round(remainingSteps / (project.metrics.trainingSpeed || 1)));

          // Periodic chart history update (every ~10-15 steps or so)
          const shouldAddHistoryPoint = project.metrics.history.length === 0 || 
            newStep - project.metrics.history[project.metrics.history.length - 1].step >= 80;

          let newHistory = project.metrics.history;
          if (shouldAddHistoryPoint) {
            const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const newPoint: MetricHistoryPoint = {
              step: newStep,
              loss: newLoss,
              speed: Number((project.metrics.trainingSpeed + (Math.random() * 0.6 - 0.3)).toFixed(1)),
              clusterCpuUtil: Math.min(99, Math.max(45, Math.round(72 + Math.random() * 12))),
              clusterGpuUtil: Math.min(99, Math.max(60, Math.round(91 + Math.random() * 7))),
              ramUtilGB: Number((26.4 + (Math.random() * 1.2)).toFixed(1)),
              timestamp: timeStr,
            };
            newHistory = [...project.metrics.history.slice(-40), newPoint];
          }

          // Update worker step counts and heartbeats
          const updatedWorkers = project.workers.map((w) => {
            if (w.status === 'training' && w.contributionStatus === 'active') {
              return {
                ...w,
                stepsProcessed: w.stepsProcessed + Math.round(stepIncrement / activeWorkers.length),
                lastHeartbeat: 'Just now',
              };
            }
            return w;
          });

          // Occasional checkpoint log
          let newLogs = project.logs;
          if (newStep % 1000 < stepIncrement) {
            const checkpointLog: TrainingEvent = {
              id: `log-chk-${Date.now()}`,
              timestamp: new Date().toLocaleTimeString(),
              type: 'checkpoint',
              message: `Automatic distributed checkpoint saved at step ${newStep.toLocaleString()} (Loss: ${newLoss}). Weights verified across ${activeWorkers.length} nodes.`,
            };
            newLogs = [checkpointLog, ...newLogs.slice(0, 49)];
          }

          return {
            ...project,
            status: isFinished ? ('completed' as const) : project.status,
            metrics: {
              ...project.metrics,
              currentStep: newStep,
              progressPercent: newPercent,
              currentLoss: newLoss,
              elapsedTimeSeconds: newElapsed,
              estimatedRemainingSeconds: estimatedRemaining,
              history: newHistory,
            },
            workers: updatedWorkers,
            logs: newLogs,
          };
        });

        return hasChanges ? updated : currentProjects;
      });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [appSettings.appPreferences.enableLiveUpdates, appSettings.appPreferences.simulationSpeed]);

  const unreadNotificationCount = useMemo(() => {
    return notifications.filter((n) => !n.read).length;
  }, [notifications]);

  return (
    <AppContext.Provider
      value={{
        projects,
        activeProjectId,
        activeProject,
        currentUserRole,
        userProfile,
        hardwareProfile,
        contributionSettings,
        appSettings,
        notifications,
        unreadNotificationCount,
        setActiveProjectId,
        setUserRole: setCurrentUserRole,
        createProject,
        joinProjectAsWorker,
        pauseWorkerContribution,
        resumeWorkerContribution,
        stopWorkerContribution,
        pauseProjectTraining,
        resumeProjectTraining,
        stopProjectTraining,
        stopProjectAsMaster,
        updateContributionSettings,
        updateUserProfile,
        updateAppSettings,
        setTheme,
        markNotificationRead,
        markAllNotificationsRead,
        clearAllNotifications,
        addNotification,
        resetDemoData,
        getProjectById,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
