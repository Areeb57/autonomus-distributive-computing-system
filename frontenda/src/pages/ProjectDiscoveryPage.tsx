import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, Server, Plus } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { ProjectCard } from '../components/cards/ProjectCard';

type FilterType = 'all' | 'online' | 'looking_for_workers' | 'training';

export const ProjectDiscoveryPage: React.FC = () => {
  const navigate = useNavigate();
  const { projects } = useApp();

  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');

  const filteredProjects = projects.filter((project) => {
    // Status filter
    if (activeFilter === 'online' && project.status !== 'online') return false;
    if (activeFilter === 'looking_for_workers' && project.status !== 'looking_for_workers') return false;
    if (activeFilter === 'training' && project.status !== 'training') return false;

    // Search query matching name, architecture, dataset, description
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = project.name.toLowerCase().includes(q);
      const matchArch = project.modelArchitecture.toLowerCase().includes(q);
      const matchDataset = project.datasetName.toLowerCase().includes(q);
      const matchDesc = project.description.toLowerCase().includes(q);
      if (!matchName && !matchArch && !matchDataset && !matchDesc) return false;
    }

    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }} className="animate-fade-in">
      {/* Header & Create Project CTA */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: 6 }}>
            Discover Distributed AI Projects
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Find active training runs seeking volunteer compute nodes or inspect cluster workloads.
          </p>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() => navigate('/create-project')}
        >
          <Plus size={16} />
          <span>Start New Project as Master</span>
        </button>
      </div>

      {/* Search & Filter Bar */}
      <div
        className="card"
        style={{
          padding: '16px 20px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
        }}
      >
        {/* Search Input */}
        <div style={{ position: 'relative', flex: 1, minWidth: 260 }}>
          <Search
            size={18}
            style={{
              position: 'absolute',
              left: 14,
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)',
            }}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Search by project name, model architecture, dataset..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: 42, width: '100%' }}
          />
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)', fontSize: '0.82rem', marginRight: 4 }}>
            <Filter size={15} />
            <span>Filter:</span>
          </div>

          <div
            style={{
              display: 'flex',
              backgroundColor: 'var(--bg-input)',
              padding: 3,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              gap: 2,
            }}
          >
            {[
              { id: 'all', label: 'All Projects' },
              { id: 'online', label: 'Online' },
              { id: 'looking_for_workers', label: 'Looking for Workers' },
              { id: 'training', label: 'Training in Progress' },
            ].map((f) => (
              <button
                key={f.id}
                className={`btn btn-sm ${activeFilter === f.id ? 'btn-primary' : 'btn-outline'}`}
                style={{
                  border: 'none',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-sm)',
                  boxShadow: activeFilter === f.id ? undefined : 'none',
                  fontSize: '0.8rem',
                }}
                onClick={() => setActiveFilter(f.id as FilterType)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Projects Grid */}
      {filteredProjects.length === 0 ? (
        <div
          className="card"
          style={{
            padding: '64px 20px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: '50%',
              backgroundColor: 'var(--bg-card-hover)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <Server size={24} />
          </div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600 }}>No projects found</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: 420 }}>
            No projects matched your search criteria. Try modifying your search keywords or resetting the filter.
          </p>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setSearchQuery('');
              setActiveFilter('all');
            }}
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: 22,
          }}
        >
          {filteredProjects.map((project) => {
            const isUserMember = project.workers.some((w) => w.isCurrentUser);
            const isUserMaster = project.owner.isCurrentUser;

            return (
              <ProjectCard
                key={project.id}
                project={project}
                onView={(id) => navigate(`/projects/${id}`)}
                onJoin={(id) => navigate(`/worker-setup/${id}`)}
                isUserMember={isUserMember}
                isUserMaster={isUserMaster}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};
