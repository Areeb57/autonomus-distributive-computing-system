import type { MetricHistoryPoint, TrainingMetrics } from '../types';

export const generateInitialMetricsHistory = (): MetricHistoryPoint[] => {
  const points: MetricHistoryPoint[] = [];
  const baseLoss = 0.85;
  const targetLoss = 0.082;
  const totalPoints = 35;
  
  for (let i = 0; i <= totalPoints; i++) {
    const step = Math.round((i / totalPoints) * 4200);
    const progressFactor = i / totalPoints;
    const loss = Number((targetLoss + (baseLoss - targetLoss) * Math.exp(-2.8 * progressFactor) + (Math.random() * 0.015 - 0.007)).toFixed(4));
    const speed = Number((11.2 + Math.sin(i / 3) * 1.4 + Math.random() * 0.6).toFixed(1));
    const clusterCpuUtil = Math.round(68 + Math.sin(i / 2) * 12 + Math.random() * 5);
    const clusterGpuUtil = Math.round(88 + Math.cos(i / 2.5) * 6 + Math.random() * 4);
    const ramUtilGB = Number((24.5 + progressFactor * 4.2 + (Math.random() * 0.8)).toFixed(1));
    
    const minutesAgo = Math.round((totalPoints - i) * 3.5);
    const time = new Date(Date.now() - minutesAgo * 60 * 1000);
    const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    points.push({
      step,
      loss: Math.max(0.02, loss),
      speed,
      clusterCpuUtil: Math.min(99, Math.max(40, clusterCpuUtil)),
      clusterGpuUtil: Math.min(99, Math.max(50, clusterGpuUtil)),
      ramUtilGB,
      timestamp: timeStr,
    });
  }
  return points;
};

export const defaultTrainingMetrics: TrainingMetrics = {
  currentStep: 4200,
  totalSteps: 10000,
  progressPercent: 42,
  currentLoss: 0.082,
  trainingSpeed: 12.4,
  elapsedTimeSeconds: 5240,
  estimatedRemainingSeconds: 7120,
  history: generateInitialMetricsHistory(),
};
