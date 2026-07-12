import { HashRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import Onboarding from './pages/Onboarding';
import Dashboard from './pages/Dashboard';
import { Sparkles, LayoutDashboard, UserCheck, Code, Activity } from 'lucide-react';

function Sidebar() {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand/Logo Section */}
        <div className="h-20 flex items-center gap-3 px-6 border-b border-gray-800">
          <div className="w-9 h-9 bg-blue-600/10 border border-blue-500/30 rounded-xl flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-blue-500" />
          </div>
          <span className="font-bold text-lg text-white tracking-tight">
            Mergen Yönetim Paneli
          </span>
        </div>

        {/* Navigation Section */}
        <nav className="p-4 space-y-1.5">
          <div className="px-3 mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Yönlendirme
          </div>
          <Link
            to="/onboarding"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/onboarding')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
            }`}
          >
            <UserCheck className="w-5 h-5" />
            Yeni Müşteri Kaydı
          </Link>

          <Link
            to="/dashboard"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/dashboard')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
            }`}
          >
            <LayoutDashboard className="w-5 h-5" />
            Kontrol Paneli
          </Link>
        </nav>
      </div>

      {/* Footer Version Info */}
      <div className="p-4 border-t border-gray-800 flex items-center justify-between text-xs text-gray-500 font-mono">
        <span className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-emerald-500" />
          Sistem Aktif
        </span>
        <span className="flex items-center gap-1">
          <Code className="w-3 h-3" />
          v7.2.0
        </span>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-950 flex font-sans">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Content Area */}
        <main className="flex-grow h-screen overflow-y-auto">
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
