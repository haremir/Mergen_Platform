import { HashRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import Onboarding from './pages/Onboarding';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Analytics from './pages/Analytics';
import KatipOverview from './pages/KatipOverview';
import { Sparkles, LayoutDashboard, UserCheck, Code, Activity, Settings as SettingsGear, BarChart3, FileText } from 'lucide-react';

function Sidebar() {
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="h-20 flex items-center gap-3 px-6 border-b border-slate-800">
          <div className="w-9 h-9 bg-blue-600/10 border border-blue-500/30 rounded-xl flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-blue-500" />
          </div>
          <span className="font-bold text-lg text-white tracking-tight">
            Mergen Yönetim Paneli
          </span>
        </div>

        {/* Navigation Section */}
        <nav className="p-4 space-y-1.5">
          <div className="px-3 mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Yönlendirme
          </div>
          
          <Link
            to="/onboarding"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/onboarding')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
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
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <LayoutDashboard className="w-5 h-5" />
            Kontrol Paneli
          </Link>

          <Link
            to="/katip"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/katip')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <FileText className="w-5 h-5" />
            Kâtip AI Modülü
          </Link>

          <Link
            to="/analytics"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/analytics')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <BarChart3 className="w-5 h-5" />
            Analiz ve Performans
          </Link>

          <Link
            to="/settings"
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
              isActive('/settings')
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <SettingsGear className="w-5 h-5" />
            Sistem Ayarları
          </Link>
        </nav>
      </div>

      {/* Footer System Status Info */}
      <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500 font-mono">
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
      <div className="min-h-screen bg-slate-950 flex font-sans">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Content Area */}
        <main className="flex-grow h-screen overflow-y-auto">
          <Routes>
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/katip" element={<KatipOverview />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="*" element={<Navigate to="/onboarding" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
