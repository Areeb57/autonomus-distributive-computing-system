import React, { createContext, useContext, useState, useEffect, useRef, useTransition, useCallback } from 'react';
import type {
  Role,
  MasterProject,
  WorkerProject,
  GlobalResourceSettings,
  UserSettings,
  HardwareSpecs,
  WorkerAllocation
} from '../types';
import {
  storageService,
  HARDWARE_SPECS,
  MOCK_WORKERS
} from '../services/storage';
import { api } from '../services/api';
import { agentClient } from '../services/agent';
import { generateProjectCode, cleanProjectCode } from '../utils/formatting';

interface AppContextType {
  role: Role;
  setRole: (role: Role) => void;
  simulateRoleConnection: (role: Role) => void;
  masterProject: MasterProject | null;
  workerProject: WorkerProject | null;
  resourceSettings: GlobalResourceSettings;
  userSettings: UserSettings;
  hardwareSpecs: HardwareSpecs;
  backendOnline: boolean;
  refreshBackend: () => Promise<void>;
  pendingMasterDraft: {
    name: string;
    description: string;
    datasetFileName: string;
    datasetFileSize: string;
    codeFileName: string;
    codeFileSize: string;
  } | null;
  setPendingMasterDraft: (draft: AppContextType['pendingMasterDraft']) => void;
  saveMasterDraft: (data: {
    name: string;
    description: string;
    datasetFileName: string;
    datasetFileSize: string;
    codeFileName: string;
    codeFileSize: string;
  }) => void;
  putMasterProjectOnline: () => Promise<MasterProject>;
  updateMasterControls: (action: 'pause' | 'resume' | 'stop' | 'end') => void;
  joinWorkerProject: (
    projectCode: string,
    allocation: WorkerAllocation
  ) => Promise<{ success: boolean; error?: string }>;
  updateWorkerControls: (action: 'pause' | 'resume' | 'stop') => void;
  updateResourceSettings: (newSettings: Partial<GlobalResourceSettings>) => void;
  updateUserSettings: (newSettings: Partial<UserSettings>) => void;
  toggleTheme: () => void;
  resetDemo: () => void;
  // Temporary storage for worker join code between step A and step B
  pendingWorkerCode: string;
  setPendingWorkerCode: (code: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [, startTransition] = useTransition();

  const [role, setRoleState] = useState<Role>(() => storageService.getRole());
  const [masterProject, setMasterProjectState] = useState<MasterProject | null>(() =>
    storageService.getMasterProject()
  );
  const [workerProject, setWorkerProjectState] = useState<WorkerProject | null>(() =>
    storageService.getWorkerProject()
  );
  const [resourceSettings, setResourceSettingsState] = useState<GlobalResourceSettings>(() =>
    storageService.getResourceSettings()
  );
  const [userSettings, setUserSettingsState] = useState<UserSettings>(() =>
    storageService.getUserSettings()
  );
  const [hardwareSpecs, setHardwareSpecs] = useState<HardwareSpecs>(HARDWARE_SPECS);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);

  const [pendingMasterDraft, setPendingMasterDraft] = useState<{
    name: string;
    description: string;
    datasetFileName: string;
    datasetFileSize: string;
    codeFileName: string;
    codeFileSize: string;
  } | null>(null);

  const [pendingWorkerCode, setPendingWorkerCode] = useState<string>('');

  // Synchronize document theme class
  useEffect(() => {
    if (userSettings.theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [userSettings.theme]);

  // Check backend health & hydrate state
  const refreshBackend = useCallback(async () => {
    try {
      const isHealthy = await api.checkHealth();
      setBackendOnline(isHealthy);

      if (isHealthy) {
        await api.ensureAuthenticated();

        // 1. Fetch hardware & resources
        try {
          const { hardware, settings } = await api.getHardwareAndResources();
          setHardwareSpecs(hardware);
          setResourceSettingsState(settings);
          storageService.setResourceSettings(settings);
        } catch {
          // ignore resource fetch error
        }

        // 2. Fetch projects from backend if user has one
        try {
          const backendProjects = await api.getProjects();
          if (backendProjects.length > 0) {
            const active = backendProjects[0];
            setMasterProjectState(active);
            storageService.setMasterProject(active);
          }
        } catch {
          // ignore projects fetch error
        }
      }
    } catch {
      setBackendOnline(false);
    }
  }, []);

  useEffect(() => {
    refreshBackend();
  }, [refreshBackend]);

  const setRole = (newRole: Role) => {
    storageService.setRole(newRole);
    setRoleState(newRole);
    if (backendOnline && (newRole === 'master' || newRole === 'worker')) {
      api.ensureMachinePaired(newRole).catch(() => { });
    }
  };

  const simulateRoleConnection = (newRole: Role) => {
    setRole(newRole);
  };

  // ── Local Python agent sync ───────────────────────────────────────────────
  // While adc_agent.py is running, the role chosen in the agent is the source
  // of truth. If the agent was connected and then goes away, fall back to 'none'
  // (the start screen). If it was never running, the demo buttons keep working.
  const setRoleRef = useRef(setRole);
  useEffect(() => {
    setRoleRef.current = setRole;
  });

  useEffect(() => {
    let cancelled = false;
    let wasConnected = false;

    const poll = async () => {
      const status = await agentClient.getStatus();
      if (cancelled) return;
      if (status) {
        wasConnected = true;
        if (status.role !== storageService.getRole()) {
          setRoleRef.current(status.role);
        }
      } else if (wasConnected) {
        wasConnected = false;
        if (storageService.getRole() !== 'none') {
          setRoleRef.current('none');
        }
      }
    };

    poll();
    const id = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const saveMasterDraft = (data: {
    name: string;
    description: string;
    datasetFileName: string;
    datasetFileSize: string;
    codeFileName: string;
    codeFileSize: string;
  }) => {
    setPendingMasterDraft(data);
  };

  const putMasterProjectOnline = async (): Promise<MasterProject> => {
    const draft = {
      name: pendingMasterDraft?.name || masterProject?.name || 'Distributed Training Job',
      description: pendingMasterDraft?.description || masterProject?.description || '',
      datasetFileName:
        pendingMasterDraft?.datasetFileName || masterProject?.datasetFileName || 'dataset.zip',
      datasetFileSize:
        pendingMasterDraft?.datasetFileSize || masterProject?.datasetFileSize || '500 MB',
      codeFileName: pendingMasterDraft?.codeFileName || masterProject?.codeFileName || 'train.py',
      codeFileSize: pendingMasterDraft?.codeFileSize || masterProject?.codeFileSize || '12 KB'
    };

    // If backend is online, create and put online via real backend API
    if (backendOnline) {
      try {
        await api.ensureMachinePaired('master');
        const created = await api.createProject(draft);
        const onlineRes = await api.putProjectOnline(created.id);

        const project: MasterProject = {
          ...onlineRes.project,
          name: draft.name,
          description: draft.description,
          datasetFileName: draft.datasetFileName,
          datasetFileSize: draft.datasetFileSize,
          codeFileName: draft.codeFileName,
          codeFileSize: draft.codeFileSize,
          workers: onlineRes.project.workers?.length ? onlineRes.project.workers : [...MOCK_WORKERS]
        };

        storageService.setMasterProject(project);
        setMasterProjectState(project);
        setPendingMasterDraft(null);
        // Tell adc_agent.py to become the master for this backend project.
        // Keep project creation usable if the local agent is not running; surface a console warning.
        agentClient.setRole('master', project.id).catch((err) => {
          console.warn('Project is online, but the local ADC agent could not be switched to Master:', err);
        });
        return project;
      } catch (err) {
        console.warn('Backend put online failed, falling back to local mode:', err);
      }
    }

    // Local fallback
    const existingCode = masterProject?.projectCode;
    const projectCode =
      existingCode && existingCode.length === 9 ? existingCode : generateProjectCode();

    const newProject: MasterProject = {
      id: masterProject?.id || 'proj-' + Date.now(),
      name: draft.name,
      description: draft.description,
      datasetFileName: draft.datasetFileName,
      datasetFileSize: draft.datasetFileSize,
      codeFileName: draft.codeFileName,
      codeFileSize: draft.codeFileSize,
      projectCode,
      status: 'training',
      progress: masterProject?.progress ?? 0.0,
      currentStep: masterProject?.currentStep ?? 0,
      totalSteps: 4000,
      loss: masterProject?.loss ?? 1.845,
      speed: '172 samples/s',
      elapsedSeconds: masterProject?.elapsedSeconds ?? 0,
      estimatedRemainingSeconds: 5800,
      createdAt: masterProject?.createdAt || new Date().toISOString(),
      workers: masterProject?.workers?.length ? masterProject.workers : [...MOCK_WORKERS]
    };

    storageService.setMasterProject(newProject);
    setMasterProjectState(newProject);
    setPendingMasterDraft(null);
    return newProject;
  };

  const updateMasterControls = (action: 'pause' | 'resume' | 'stop' | 'end') => {
    if (!masterProject) return;

    let updated: MasterProject | null = { ...masterProject };

    if (action === 'pause') {
      updated.status = 'paused';
    } else if (action === 'resume') {
      updated.status = 'training';
    } else if (action === 'stop') {
      updated.status = 'stopped';
    } else if (action === 'end') {
      updated = null;
    }

    storageService.setMasterProject(updated);
    setMasterProjectState(updated);

    // Call backend API asynchronously if online
    if (backendOnline && masterProject.id && !masterProject.id.startsWith('proj-')) {
      if (action === 'pause') {
        api.pauseProject(masterProject.id).catch(() => { });
      } else if (action === 'resume') {
        api.resumeProject(masterProject.id).catch(() => { });
      } else if (action === 'stop') {
        api.stopProject(masterProject.id).catch(() => { });
      } else if (action === 'end') {
        api.endProject(masterProject.id).catch(() => { });
      }
    }
  };

  const joinWorkerProject = async (
    code: string,
    allocation: WorkerAllocation
  ): Promise<{ success: boolean; error?: string }> => {
    const rawCode = cleanProjectCode(code);
    if (rawCode.length !== 9) {
      return { success: false, error: 'Project code must be exactly 9 numeric digits.' };
    }

    // If backend is online, attempt real join by code
    if (backendOnline) {
      const backendRes = await api.joinByCode(rawCode, allocation);
      if (backendRes.success && backendRes.workerProject) {
        storageService.setWorkerProject(backendRes.workerProject);
        setWorkerProjectState(backendRes.workerProject);
        setPendingWorkerCode('');
        try {
          await api.connectPendingWorkerAgent();
        } catch (err) {
          return {
            success: false,
            error: `Project membership was accepted, but the local agent could not start the WebRTC connection: ${err instanceof Error ? err.message : 'unknown error'}. Make sure adc_agent.py is running and the backend WebRTC signaling endpoints are available.`
          };
        }
        return { success: true };
      }
      return { success: false, error: backendRes.error || 'The backend did not accept the project join request.' };
    }

    // Offline / Demo fallback
    const currentMaster = storageService.getMasterProject();
    let projectName = 'Distributed Training Cluster';

    if (currentMaster && currentMaster.projectCode === rawCode) {
      projectName = currentMaster.name;
    } else if (currentMaster && currentMaster.projectCode !== rawCode && !backendOnline) {
      return {
        success: false,
        error: `No online project found with code ${rawCode}. (Active Master project code is ${currentMaster.projectCode})`
      };
    } else {
      projectName = `AI Training Cluster #${rawCode.slice(0, 4)}`;
    }

    const workerProj: WorkerProject = {
      projectCode: rawCode,
      projectName,
      allocation,
      status: 'computing',
      assignedTask: 'DDP Gradient Sync (Workers 1-4) • Batch 1,424',
      currentProgress: currentMaster?.progress || 18.5,
      currentStep: currentMaster?.currentStep || 740,
      totalSteps: 4000,
      cpuUsage: Math.min(Math.round(allocation.cpuPercent * 0.88), 92),
      ramUsageGb: Math.round(allocation.ramGb * 0.75 * 10) / 10,
      gpuUsage: Math.min(Math.round(allocation.gpuPercent * 0.92), 95),
      joinedAt: new Date().toISOString()
    };

    storageService.setWorkerProject(workerProj);
    setWorkerProjectState(workerProj);
    setPendingWorkerCode('');
    return { success: true };
  };

  const updateWorkerControls = (action: 'pause' | 'resume' | 'stop') => {
    if (!workerProject) return;

    if (action === 'stop') {
      storageService.setWorkerProject(null);
      setWorkerProjectState(null);
      return;
    }

    const updated: WorkerProject = {
      ...workerProject,
      status: action === 'pause' ? 'paused' : 'computing'
    };

    storageService.setWorkerProject(updated);
    setWorkerProjectState(updated);
  };

  const updateResourceSettings = (newSettings: Partial<GlobalResourceSettings>) => {
    const updated = { ...resourceSettings, ...newSettings };
    storageService.setResourceSettings(updated);
    setResourceSettingsState(updated);

    if (backendOnline) {
      api.updateResourceSettings(newSettings).catch(() => { });
    }
  };

  const updateUserSettings = (newSettings: Partial<UserSettings>) => {
    const updated = { ...userSettings, ...newSettings };
    storageService.setUserSettings(updated);
    setUserSettingsState(updated);
  };

  const toggleTheme = () => {
    const nextTheme = userSettings.theme === 'dark' ? 'light' : 'dark';
    updateUserSettings({ theme: nextTheme });
  };

  const resetDemo = () => {
    storageService.resetDemo();
    setRoleState('none');
    setMasterProjectState(null);
    setWorkerProjectState(null);
    setResourceSettingsState(storageService.getResourceSettings());
    setUserSettingsState(storageService.getUserSettings());
    setPendingMasterDraft(null);
    setPendingWorkerCode('');
  };

  // Real-time WebSocket connection to backend
  useEffect(() => {
    if (!backendOnline) return;

    const currentProjectId = masterProject?.id || null;
    const unsubscribe = api.connectWebSocket(
      currentProjectId,
      (event) => {
        startTransition(() => {
          if (event.type === 'training.progress' && event.data) {
            const data = event.data;
            if (role === 'master') {
              setMasterProjectState((prev) => {
                if (!prev) return null;
                const nextStep = data.step ?? prev.currentStep;
                const total = data.totalSteps ?? prev.totalSteps;
                const progress = data.progressPercent ?? parseFloat(((nextStep / total) * 100).toFixed(1));
                const loss = data.loss ?? prev.loss;
                const speed = data.speed ? `${Math.round(data.speed)} samples/s` : prev.speed;

                const updated: MasterProject = {
                  ...prev,
                  currentStep: nextStep,
                  totalSteps: total,
                  progress,
                  loss,
                  speed
                };
                storageService.setMasterProject(updated);
                return updated;
              });
            } else if (role === 'worker') {
              setWorkerProjectState((prev) => {
                if (!prev) return null;
                const nextStep = data.step ?? prev.currentStep;
                const total = data.totalSteps ?? prev.totalSteps;
                const progress = data.progressPercent ?? parseFloat(((nextStep / total) * 100).toFixed(1));

                const updated: WorkerProject = {
                  ...prev,
                  currentStep: nextStep,
                  totalSteps: total,
                  currentProgress: progress,
                  cpuUsage: data.clusterCpuUtil ?? prev.cpuUsage,
                  gpuUsage: data.clusterGpuUtil ?? prev.gpuUsage
                };
                storageService.setWorkerProject(updated);
                return updated;
              });
            }
          } else if (event.type === 'project.status_changed' && event.data?.status) {
            const newStatus = event.data.status as MasterProject['status'];
            setMasterProjectState((prev) => {
              if (!prev) return null;
              const updated = { ...prev, status: newStatus };
              storageService.setMasterProject(updated);
              return updated;
            });
          }
        });
      },
      (isConnected) => {
        setBackendOnline(isConnected);
      }
    );

    return () => {
      unsubscribe();
    };
  }, [backendOnline, masterProject?.id, role]);

  // Local simulation ticker when offline
  useEffect(() => {
    if (backendOnline) return;

    const interval = setInterval(() => {
      startTransition(() => {
        const isGlobalPaused = resourceSettings.globalPaused;

        // 1. Master simulation ticker
        setMasterProjectState((prev) => {
          if (!prev) return null;
          if (prev.status !== 'training' || isGlobalPaused) return prev;

          const nextStep = prev.currentStep + 1;
          if (nextStep > prev.totalSteps) {
            const finished = { ...prev, status: 'online' as const, progress: 100 };
            storageService.setMasterProject(finished);
            return finished;
          }

          const nextProgress = Math.min(
            parseFloat(((nextStep / prev.totalSteps) * 100).toFixed(1)),
            100
          );
          const targetLoss = 0.22;
          const nextLoss = Math.max(
            parseFloat((prev.loss - 0.0004 + (Math.random() * 0.0002 - 0.0001)).toFixed(4)),
            targetLoss
          );

          const updated: MasterProject = {
            ...prev,
            currentStep: nextStep,
            progress: nextProgress,
            loss: nextLoss,
            elapsedSeconds: prev.elapsedSeconds + 1,
            estimatedRemainingSeconds: Math.max(prev.estimatedRemainingSeconds - 1, 0)
          };
          storageService.setMasterProject(updated);
          return updated;
        });

        // 2. Worker simulation ticker
        setWorkerProjectState((prev) => {
          if (!prev) return null;
          if (prev.status !== 'computing' || isGlobalPaused) return prev;

          const nextStep = prev.currentStep + 1;
          const nextProgress = Math.min(
            parseFloat(((nextStep / prev.totalSteps) * 100).toFixed(1)),
            100
          );

          const cpuJitter = Math.floor(Math.random() * 7) - 3;
          const gpuJitter = Math.floor(Math.random() * 5) - 2;
          const ramJitter = Math.random() * 0.4 - 0.2;

          const baseCpu = Math.round(prev.allocation.cpuPercent * 0.85);
          const baseGpu = Math.round(prev.allocation.gpuPercent * 0.9);
          const baseRam = prev.allocation.ramGb * 0.72;

          const updated: WorkerProject = {
            ...prev,
            currentStep: nextStep,
            currentProgress: nextProgress,
            cpuUsage: Math.max(10, Math.min(99, baseCpu + cpuJitter)),
            gpuUsage: Math.max(10, Math.min(99, baseGpu + gpuJitter)),
            ramUsageGb: Math.max(
              1,
              Math.min(prev.allocation.ramGb, parseFloat((baseRam + ramJitter).toFixed(1)))
            )
          };
          storageService.setWorkerProject(updated);
          return updated;
        });
      });
    }, 1500);

    return () => clearInterval(interval);
  }, [backendOnline, resourceSettings.globalPaused]);

  return (
    <AppContext.Provider
      value={{
        role,
        setRole,
        simulateRoleConnection,
        masterProject,
        workerProject,
        resourceSettings,
        userSettings,
        hardwareSpecs,
        backendOnline,
        refreshBackend,
        pendingMasterDraft,
        setPendingMasterDraft,
        saveMasterDraft,
        putMasterProjectOnline,
        updateMasterControls,
        joinWorkerProject,
        updateWorkerControls,
        updateResourceSettings,
        updateUserSettings,
        toggleTheme,
        resetDemo,
        pendingWorkerCode,
        setPendingWorkerCode
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
