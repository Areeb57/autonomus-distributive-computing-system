import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { DashboardPage } from '../pages/DashboardPage';
import { CreateProjectPage } from '../pages/CreateProjectPage';
import { ProjectDiscoveryPage } from '../pages/ProjectDiscoveryPage';
import { WorkerSetupPage } from '../pages/WorkerSetupPage';
import { HardwareProfilePage } from '../pages/HardwareProfilePage';
import { ResourceSelectionPage } from '../pages/ResourceSelectionPage';
import { ProjectProgressPage } from '../pages/ProjectProgressPage';
import { ResourceSettingsPage } from '../pages/ResourceSettingsPage';
import { SettingsPage } from '../pages/SettingsPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: 'projects',
        element: <ProjectDiscoveryPage />,
      },
      {
        path: 'projects/:projectId',
        element: <ProjectProgressPage />,
      },
      {
        path: 'my-project',
        element: <ProjectProgressPage />,
      },
      {
        path: 'create-project',
        element: <CreateProjectPage />,
      },
      {
        path: 'worker-setup/:projectId',
        element: <WorkerSetupPage />,
      },
      {
        path: 'worker-hardware/:projectId',
        element: <HardwareProfilePage />,
      },
      {
        path: 'worker-resources/:projectId',
        element: <ResourceSelectionPage />,
      },
      {
        path: 'resources',
        element: <ResourceSettingsPage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      {
        path: '*',
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);
