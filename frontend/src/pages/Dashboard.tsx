import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getLogs, getPlan } from '../api';
import type { LogEntry, PlanResult } from '../api';
import { 
  Terminal, ShieldCheck, Cpu, RefreshCw, 
  MessageSquare, User, Bot, AlertTriangle 
} from 'lucide-react';

export default function Dashboard() {
  const [searchParams] = useSearchParams();
  // Read tenant_id from either the search parameters or fallback to a local storage or state
  const [tenantId, setTenantId] = useState<string>(
    searchParams.get('tenant_id') || '4cc9eef0-82eb-54ea-9999-desktest9999'
  );

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchDashboardData = async (targetId: string) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [logsData, planData] = await Promise.all([
        getLogs(targetId),
        getPlan(targetId)
      ]);
      setLogs(logsData.messages);
      setPlan(planData);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(
        err.response?.data?.detail || 
        err.message || 
        'Failed to retrieve backend data. Make sure panel API server is running.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tenantId) {
      fetchDashboardData(tenantId);
    }
  }, [tenantId]);

  const handleRefresh = () => {
    if (tenantId) fetchDashboardData(tenantId);
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-4">
      {/* Upper Panel */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-extrabold text-white flex items-center gap-3">
            <Cpu className="w-8 h-8 text-violet-500" />
            Desk Intelligence Panel
          </h1>
          <p className="text-gray-400 mt-1">
            Realtime monitoring of AI chatbot conversations and subscription limits.
          </p>
        </div>
        
        {/* Tenant Switcher */}
        <div className="flex items-center gap-3 bg-[#12131a] border border-[#23242f] px-3 py-2 rounded-xl w-full sm:w-auto">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tenant:</span>
          <input
            type="text"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            placeholder="Enter Tenant UUID"
            className="bg-[#181922] border border-[#2b2c3a] text-xs font-mono text-white px-3 py-1.5 rounded-lg w-full sm:w-60 focus:outline-none focus:border-violet-500"
          />
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="p-2 hover:bg-[#1f202b] text-gray-400 hover:text-white rounded-lg transition-colors cursor-pointer"
            title="Refresh logs & plan"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="bg-[#2a1215] border border-[#ef444450] text-[#ef4444] rounded-xl p-4 flex items-start gap-3 mb-8">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm font-medium">
            <p className="font-semibold">Backend Connection Issue</p>
            <p className="opacity-90 mt-1">{errorMsg}</p>
          </div>
        </div>
      )}

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Right side: Plan limits (1 col) */}
        <div className="space-y-6">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 mb-4">
            <ShieldCheck className="w-5 h-5 text-violet-500" />
            Quota & Limits
          </h2>

          <div className="bg-[#12131a] border border-[#23242f] rounded-2xl p-6 space-y-6">
            <div>
              <span className="text-xs font-semibold text-gray-500 block uppercase tracking-wider">Active Plan</span>
              <span className="text-2xl font-bold text-white capitalize">{plan?.plan || 'starter'}</span>
            </div>

            {plan ? (
              Object.entries(plan.limits).map(([key, limitVal]) => {
                const percent = Math.min(100, Math.round((limitVal.used / limitVal.limit) * 100));
                return (
                  <div key={key} className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400 capitalize">{key.replace('_', ' ')}</span>
                      <span className="text-white font-medium">
                        {limitVal.used} / {limitVal.limit} {limitVal.unit.split('/')[0]}
                      </span>
                    </div>
                    {/* Progress Bar */}
                    <div className="w-full bg-[#181922] h-2.5 rounded-full overflow-hidden border border-[#2b2c3a]">
                      <div 
                        className={`h-full rounded-full transition-all duration-500 ${
                          percent > 90 ? 'bg-red-500' : percent > 75 ? 'bg-yellow-500' : 'bg-violet-600'
                        }`} 
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>{percent}% consumed</span>
                      <span>{limitVal.remaining} remaining</span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-gray-500 text-sm py-4">No plan configurations loaded.</div>
            )}
            
            <div className="border-t border-[#23242f] pt-4 text-xs text-gray-500 italic">
              {plan?.note || 'Standard limits configured.'}
            </div>
          </div>
        </div>

        {/* Left side: Message Logs (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 mb-4">
            <Terminal className="w-5 h-5 text-violet-500" />
            Live Webhook Logs
          </h2>

          <div className="bg-[#12131a] border border-[#23242f] rounded-2xl overflow-hidden shadow-xl min-h-[400px] flex flex-col">
            <div className="bg-[#181922] px-6 py-4 border-b border-[#23242f] flex justify-between items-center shrink-0">
              <span className="text-sm font-semibold text-white">Recent events</span>
              <span className="text-xs text-gray-500 font-mono">Channel: WhatsApp</span>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 flex-grow max-h-[500px]">
              {logs.length > 0 ? (
                logs.map((log) => {
                  const isInbound = log.direction === 'inbound';
                  return (
                    <div 
                      key={log.message_id} 
                      className={`flex gap-4 p-4 rounded-xl border transition-colors ${
                        isInbound 
                          ? 'bg-[#181922]/50 border-[#2b2c3a]/50 hover:bg-[#181922]' 
                          : 'bg-violet-500/5 border-violet-500/10 hover:bg-violet-500/10'
                      }`}
                    >
                      {/* Avatar */}
                      <div className={`w-10 h-10 rounded-full shrink-0 flex items-center justify-center border ${
                        isInbound 
                          ? 'bg-gray-800 border-gray-700 text-gray-400' 
                          : 'bg-violet-600/15 border-violet-600/30 text-violet-400'
                      }`}>
                        {isInbound ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                      </div>

                      {/* Content */}
                      <div className="flex-grow space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-white">
                            {isInbound ? `User (${log.sender})` : 'AI Receptionist'}
                          </span>
                          <span className="text-[10px] text-gray-500 font-mono">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-sm text-gray-300 break-words font-sans whitespace-pre-line leading-relaxed">
                          {log.text}
                        </p>
                        <div className="flex items-center gap-4 pt-1.5 text-[10px] text-gray-500 font-mono">
                          <span>ID: {log.message_id}</span>
                          <span>Channel: {log.channel}</span>
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
                  <MessageSquare className="w-12 h-12 text-gray-600" />
                  <p className="text-gray-500 text-sm">No webhook logs matching tenant ID.</p>
                </div>
              )}
            </div>
            
            <div className="bg-[#181922] px-6 py-4 border-t border-[#23242f] text-xs text-gray-500 text-right shrink-0">
              Mock dataset. Run client queries to view changes.
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
