import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './pages/Dashboard';
import { MasterProjectSetup } from './pages/MasterProjectSetup';
import { ProjectReview } from './pages/ProjectReview';
import { WorkerJoin } from './pages/WorkerJoin';
import { ResourceAllocation } from './pages/ResourceAllocation';
import { MyProgress } from './pages/MyProgress';
import { ResourceSettings } from './pages/ResourceSettings';
import { Settings } from './pages/Settings';

const AppLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const location = useLocation();

  const getPageTitle = (pathname: string): string => {
    if (pathname === '/') return 'Dashboard';
    if (pathname === '/master/setup') return 'Project Setup';
    if (pathname === '/master/review') return 'Review Project';
    if (pathname === '/master/progress') return 'My Progress (Master)';
    if (pathname === '/worker/join') return 'Join Project';
    if (pathname === '/worker/allocation') return 'Resource Allocation';
    if (pathname === '/worker/progress') return 'My Progress (Worker)';
    if (pathname === '/resources') return 'Resource Settings';
    if (pathname === '/settings') return 'Settings';
    return 'ADC';
  };

  return (
    <div className={`app-shell ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="main-content-wrapper">
        <Header
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title={getPageTitle(location.pathname)}
        />
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/master/setup" element={<MasterProjectSetup />} />
            <Route path="/master/review" element={<ProjectReview />} />
            <Route path="/master/progress" element={<MyProgress />} />
            <Route path="/worker/join" element={<WorkerJoin />} />
            <Route path="/worker/allocation" element={<ResourceAllocation />} />
            <Route path="/worker/progress" element={<MyProgress />} />
            <Route path="/resources" element={<ResourceSettings />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <AppLayout />
      </BrowserRouter>
    </AppProvider>
  );
}
