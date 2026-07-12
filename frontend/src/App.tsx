import { HashRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import Onboarding from './pages/Onboarding';
import Dashboard from './pages/Dashboard';
import { Sparkles, LayoutDashboard, UserCheck, Code } from 'lucide-react';

function Navigation() {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <aside className="w-full lg:w-[260px] bg-[#0c0d14] border-b lg:border-b-0 lg:border-r border-[#1f202b] flex flex-col shrink-0">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-[#1f202b] select-none">
        <Sparkles className="w-6 h-6 text-violet-500 animate-pulse" />
        <span className="font-extrabold text-lg bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent tracking-wide">
          MERGEN PANEL
        </span>
      </div>

      {/* Nav Links */}
      <nav className="p-4 flex flex-row lg:flex-col gap-2 overflow-x-auto lg:overflow-x-visible shrink-0 lg:flex-grow">
        {/* Onboarding */}
        <Link
          to="/onboarding"
          className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all whitespace-nowrap ${
            isActive('/onboarding')
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/10'
              : 'text-gray-400 hover:bg-[#181922] hover:text-white'
          }`}
        >
          <UserCheck className="w-5 h-5" />
          Client Onboarding
        </Link>

        {/* Dashboard */}
        <Link
          to="/dashboard"
          className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all whitespace-nowrap ${
            isActive('/dashboard')
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/10'
              : 'text-gray-400 hover:bg-[#181922] hover:text-white'
          }`}
        >
          <LayoutDashboard className="w-5 h-5" />
          Control Panel
        </Link>
      </nav>

      {/* Bottom version badge */}
      <div className="hidden lg:flex items-center gap-2 p-6 border-t border-[#1f202b] text-[10px] text-gray-500 font-mono mt-auto">
        <Code className="w-3.5 h-3.5" />
        <span>Version 7.1.0 (Beta)</span>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-[#07080c] flex flex-col lg:flex-row font-sans">
        {/* Sidebar */}
        <Navigation />

        {/* Main Content Area */}
        <main className="flex-grow overflow-y-auto">
          <Routes>
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="*" element={<Navigate to="/onboarding" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
