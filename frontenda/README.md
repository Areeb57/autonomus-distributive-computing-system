# Autonomous Distributed AI Trainer (Frontend Prototype)

An interactive, modern, high-performance web dashboard for distributed peer-to-peer AI training. The platform enables users to coordinate computing power across machines as either a **Master** (creating and managing training jobs) or a **Worker** (volunteering CPU/RAM/GPU compute power).

> **Note:** This is a frontend-only simulation prototype. It does not require a backend server, Python daemon, or GPU cluster. All metrics, file uploads, hardware detections, and Ring-AllReduce gossips are simulated in client-side state.

---

## 🚀 Quick Start

Ensure you have **Node.js** (v18+) and **npm** installed.

```bash
# 1. Install dependencies
npm install

# 2. Start the local development server
npm run dev
```

The application will be accessible at: `http://localhost:5173/`

To test a production build:
```bash
npm run build
npm run preview
```

---

## 🛠️ Technology Stack

- **React 19 & TypeScript**: Component-driven UI with strong typing.
- **Vite**: Rapid HMR bundling.
- **React Router 7**: Multi-route SPA architecture.
- **Pure Vanilla CSS**: Custom variables design system with dark/light themes (no Tailwind CSS).
- **Lucide React**: Clean iconography for distributed compute interfaces.
- **Recharts**: Responsive real-time loss curves, throughput (steps/sec), CPU/GPU cluster utilization, and memory telemetry.
- **React Context & Hooks**: Centralized state with simulated Ring-AllReduce gossip consensus.
- **localStorage**: Full state persistence for demo projects, roles, and resource budgets.

---

## 🧭 Key Workflows & Features

### 1. Dashboard
- **Welcome & Context Banner**: Summary of distributed AI capabilities.
- **Role Detection**: Persistent indicator in the top bar (`Not participating`, `Master`, `Worker`, or `Master & Worker`).
- **Initial Visitor State**: Prominently displays two primary action cards:
  - **Start New Project as Master**: Multi-step project authoring.
  - **Work as a Worker**: Project discovery and node onboarding.
- **Active Participant State**: Displays live project name, progress bar, worker node metrics, and stop controls.
- **Cluster Telemetry**: Aggregate network metrics (Active Projects, Online Workers, Active Jobs).

### 2. Master Workflow (`/create-project`)
- **Step 1: Project Information**: Architecture selection (Diffusion UNet, Vision Transformer, LLM LoRA), training objectives, dataset description, duration, and worker targets.
- **Step 2: Upload Dataset & Model Code**: Drag-and-drop file upload zones with verified formats, simulated upload progress indicators, and training hyperparameter configurations (batch size, learning rate, precision, optimizer). Includes a **"Load Diffusion Demo Preset"** shortcut.
- **Step 3: Review & Put Project Online**: Full configuration summary with confirmation modal that broadcasts the job into the public catalogue and appoints the user as Master.
- **Step 4: Shared Progress Page**: Real-time cluster monitoring.

### 3. Worker Workflow (`/projects` -> `/worker-setup` -> `/worker-hardware` -> `/worker-resources`)
- **Step 1: Project Discovery**: Searchable by name, model architecture, dataset, or description; filterable by status (`Online`, `Looking for Workers`, `Training in Progress`).
- **Step 2: Python Worker Agent Download**: Explains agent sandboxing, security notices, and features simulated download and installation.
- **Step 3: Hardware Diagnostics**: Multi-stage scanning animation that profiles CPU cores, RAM, GPU model, VRAM capacity, and disk caching space.
- **Step 4: Resource Contribution**: Sliders for CPU core donation, RAM allocation ceiling, GPU acceleration toggle, disk budget, and network sync preferences.
- **Step 5: Join Project**: Registers the volunteer node into the cluster and redirects to the shared progress telemetry.

### 4. Shared Project Progress Page (`/projects/:id`)
- **Unified Master & Worker Experience**: Both roles access the same telemetry screen.
- **Role-Aware Controls**:
  - **Master**: Pause Training, Resume Training, Stop Training, Stop Project Management.
  - **Worker**: Pause Contribution, Resume Contribution, Withdraw Node & Stop Contributing.
  - **Observer**: Join as Worker Node CTA.
- **Telemetry Charts**: Loss curve, throughput (steps/sec), CPU/GPU cluster utilization, and cluster RAM.
- **Participating Compute Nodes**: Detailed cards for each worker node showing CPU/RAM allocations, GPU model, and current batch size.
- **Live Event & Consensus Log**: Filterable gossip stream with real-time checkpoint timestamps and alerts.

### 5. Dedicated Resource Settings (`/resources`)
- View physical machine hardware capacities separately from current volunteer allocations.
- Adjust CPU/RAM/GPU budgets, disk space, and network profiles.
- Global "Pause All Contributions" switch and "Reset to Defaults" option.

### 6. Settings & Demo Management (`/settings`)
- User Profile customization (display name, username, email, avatar).
- Theme toggle: **Dark Theme** (default slate with neon accents) and **Light Theme**.
- Simulated Notification toggles.
- Background simulation speed controls (1x, 2x, 5x).
- **Reset Demo Data**: One-click restore to clean default catalog.

---

## 📁 Source Code Structure

```text
src/
├── app/
│   └── router.tsx             # React Router configuration
├── components/
│   ├── cards/
│   │   ├── ProjectCard.tsx    # Project discovery card
│   │   ├── StatCard.tsx       # Telemetry metrics card
│   │   └── WorkerCard.tsx     # Compute node card with meters
│   ├── charts/
│   │   └── TrainingCharts.tsx # Recharts telemetry dashboard
│   ├── common/
│   │   ├── Badge.tsx          # Status and role badges
│   │   └── Modal.tsx          # Confirmation modals
│   ├── layout/
│   │   ├── MainLayout.tsx     # App wrapper
│   │   ├── Sidebar.tsx        # Persistent navigation sidebar
│   │   └── TopBar.tsx         # Title, search, role badge, theme toggle
│   ├── logs/
│   │   └── LiveLogsPanel.tsx  # Gossip event stream
│   └── progress/
│       ├── ProgressBar.tsx    # Progress indicator
│       └── Stepper.tsx        # Multi-stage workflow stepper
├── context/
│   └── AppContext.tsx         # Central state, persistence, and live simulator
├── data/
│   ├── mockHardware.ts        # Detected hardware profiles
│   ├── mockMetrics.ts         # Telemetry historical curves
│   ├── mockProjects.ts        # Default project catalog
│   └── mockWorkers.ts         # Default cluster worker nodes
├── pages/
│   ├── CreateProjectPage.tsx      # Master workflow
│   ├── DashboardPage.tsx          # Dashboard overview
│   ├── HardwareProfilePage.tsx    # Worker hardware diagnostics
│   ├── ProjectDiscoveryPage.tsx   # Project catalogue
│   ├── ProjectProgressPage.tsx    # Shared telemetry page
│   ├── ResourceSelectionPage.tsx  # Worker contribution setup
│   ├── ResourceSettingsPage.tsx   # Dedicated resource settings
│   ├── SettingsPage.tsx           # Settings & theme configuration
│   └── WorkerSetupPage.tsx        # Agent download
├── styles/
│   ├── components.css         # Buttons, cards, modals, sliders
│   ├── global.css             # Resets, animations, responsive rules
│   └── variables.css          # Design system tokens (dark/light)
├── types/
│   └── index.ts               # Complete TypeScript types
├── App.tsx                    # Root application component
├── index.css                  # Global styles loader
└── main.tsx                   # React root entry
```
