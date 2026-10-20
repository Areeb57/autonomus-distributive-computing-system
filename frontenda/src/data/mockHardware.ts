import type { HardwareProfile, ContributionSettings } from '../types';

export const mockDefaultHardware: HardwareProfile = {
  cpuModel: 'Intel Core i7-13700K (8P + 8E Cores, 24 Threads)',
  cpuCores: 16,
  ramTotalGB: 32,
  ramAvailableGB: 22,
  gpuModel: 'NVIDIA GeForce RTX 3060 Ti',
  gpuMemoryTotalGB: 12,
  diskSpaceAvailableGB: 184,
};

export const defaultContributionSettings: ContributionSettings = {
  cpuEnabled: true,
  cpuCores: 8,
  ramBudgetGB: 12,
  gpuEnabled: true,
  selectedGpu: 'NVIDIA GeForce RTX 3060 Ti',
  storageBudgetGB: 40,
  networkPreference: 'moderate',
  globalPaused: false,
};

export const mockAvailableGpus = [
  'NVIDIA GeForce RTX 3060 Ti (12 GB)',
  'Intel UHD Graphics 770 (Integrated)',
];
