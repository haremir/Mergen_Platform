import { useState, useEffect, useCallback } from "react";
import { HashRouter as Router, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { getToken, getProjectsApi } from "./lib/api";
import Sidebar, { ProjectItem } from "./components/Sidebar";
import OverviewDashboard from "./pages/OverviewDashboard";
import TopicsPage from "./pages/TopicsPage";
import DraftsPage from "./pages/DraftsPage";
import DraftEditor from "./pages/DraftEditor";
import Login from "./pages/Login";

function ProtectedRoute({ children }: { children: JSX.Element }) {
  const token = getToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function AppShell() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  const fetchProjects = useCallback(async () => {
    try {
      const data = await getProjectsApi();
      const items = data.items ?? [];
      setProjects(items);
      if (items.length > 0 && !selectedProjectId) {
        setSelectedProjectId(items[0].id);
      }
    } catch (_e) {
      console.error("Projects fetch warning", _e);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex font-sans">
      {/* Permanent Left Sidebar */}
      <Sidebar
        projects={projects}
        selectedProjectId={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        onProjectCreated={fetchProjects}
      />

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto min-h-screen">
        <Outlet context={{ selectedProjectId, setSelectedProjectId }} />
      </main>
    </div>
  );
}

export default function App() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  const fetchProjects = useCallback(async () => {
    try {
      const data = await getProjectsApi();
      const items = data.items ?? [];
      setProjects(items);
      if (items.length > 0 && !selectedProjectId) {
        setSelectedProjectId(items[0].id);
      }
    } catch (_e) {
      console.error("Projects fetch warning", _e);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* Protected Dashboard App Layout */}
        <Route
          element={
            <ProtectedRoute>
              <div className="min-h-screen bg-slate-950 text-slate-100 flex font-sans">
                <Sidebar
                  projects={projects}
                  selectedProjectId={selectedProjectId}
                  onSelectProject={setSelectedProjectId}
                  onProjectCreated={fetchProjects}
                />
                <main className="flex-1 overflow-y-auto min-h-screen">
                  <Outlet />
                </main>
              </div>
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<OverviewDashboard selectedProjectId={selectedProjectId} />} />
          <Route path="/topics" element={<TopicsPage selectedProjectId={selectedProjectId} />} />
          <Route path="/drafts" element={<DraftsPage selectedProjectId={selectedProjectId} />} />
          <Route path="/drafts/:draftId" element={<DraftEditor />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}
