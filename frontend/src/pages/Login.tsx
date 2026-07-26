import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginAdminApi } from '../api';
import { ShieldCheck, Sparkles } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Lütfen e-posta ve şifrenizi girin.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await loginAdminApi(email.trim(), password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Süper admin girişi başarısız. Bilgilerinizi kontrol edin.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600/20 border border-blue-500/30 text-blue-400 mb-2">
            <Sparkles className="w-7 h-7 text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center justify-center gap-2">
            Mergen Platform
            <span className="text-xs bg-blue-900/60 text-blue-300 border border-blue-700/50 px-2 py-0.5 rounded font-mono">
              Admin
            </span>
          </h1>
          <p className="text-sm text-slate-400">Süper Admin Yönetim Paneli Girişi</p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-4 bg-red-950/60 border border-red-800/80 rounded-xl text-red-300 text-sm flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div>{error}</div>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Admin E-posta
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@mergen.com"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Şifre
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium py-3 rounded-xl transition-all duration-200 shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 mt-2"
          >
            {loading ? 'Giriş Yapılıyor...' : 'Giriş Yap'}
          </button>
        </form>

        <div className="text-center text-xs text-slate-500 border-t border-slate-800/80 pt-4 font-mono">
          Mergen Multi-Tenant Platform v7.3.0
        </div>
      </div>
    </div>
  );
}
