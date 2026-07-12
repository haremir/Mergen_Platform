import { useState } from 'react';
import { submitOnboarding } from '../api';
import type { OnboardingPayload, OnboardingResult } from '../api';
import { 
  Building2, FileText, Sparkles, CheckCircle2, AlertCircle, RefreshCw 
} from 'lucide-react';

export default function Onboarding() {
  const [formData, setFormData] = useState<OnboardingPayload>({
    business_name: '',
    phone_number: '',
    business_hours: '',
    location: '',
    cancellation_policy: '',
    contact_info: '',
    services: '',
    pricing: '',
    plan: 'starter'
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setErrorMsg(null);

    try {
      const response = await submitOnboarding(formData);
      setResult(response);
      if (response.status !== 'pending_verification') {
        setErrorMsg(response.error || `Onboarding finished with status: ${response.status}`);
      }
    } catch (err: any) {
      console.error(err);
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          const missing = detail.map((d: any) => d.loc[d.loc.length - 1]).join(', ');
          setErrorMsg(`Validation Error: Missing or invalid fields: ${missing}`);
        } else {
          setErrorMsg(JSON.stringify(detail));
        }
      } else {
        setErrorMsg(err.message || 'An error occurred during onboarding submit.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setErrorMsg(null);
  };

  return (
    <div className="max-w-4xl mx-auto py-12 px-6 sm:px-8">
      {/* Title Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
          <Sparkles className="w-8 h-8 text-blue-500 animate-pulse" />
          Client Onboarding
        </h1>
        <p className="text-gray-400 mt-2 text-sm leading-relaxed">
          Configure a new front-desk tenant on the Mergen Platform by supplying basic contact and business policies.
        </p>
      </div>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-8">
          
          {/* Card 1: Business Identity */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 sm:p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
              <Building2 className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Business Identity</h2>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {/* Business Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Business Name *
                </label>
                <input
                  type="text"
                  name="business_name"
                  required
                  placeholder="e.g., Acme Barber Istanbul"
                  value={formData.business_name}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* WhatsApp Phone Number */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  WhatsApp Phone Number *
                </label>
                <input
                  type="text"
                  name="phone_number"
                  required
                  placeholder="e.g., +905551234567"
                  value={formData.phone_number}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>
            </div>
          </div>

          {/* Card 2: Knowledge Ingestion */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 sm:p-8 shadow-xl space-y-6">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
              <FileText className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold tracking-tight text-white">Knowledge Ingestion</h2>
            </div>

            <div className="space-y-6">
              {/* Business Hours */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Business Hours *
                </label>
                <input
                  type="text"
                  name="business_hours"
                  required
                  placeholder="e.g., Mon-Fri 09:00-19:00, Sat 10:00-17:00"
                  value={formData.business_hours}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Location */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Location / Address *
                </label>
                <input
                  type="text"
                  name="location"
                  required
                  placeholder="e.g., Kadikoy Mah. Ataturk Cad. No:12, Kadikoy/Istanbul"
                  value={formData.location}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Cancellation Policy */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Cancellation Policy *
                </label>
                <textarea
                  name="cancellation_policy"
                  required
                  rows={3}
                  placeholder="e.g., 24 hours advance notice required for cancellations."
                  value={formData.cancellation_policy}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
                />
              </div>

              {/* Contact Info */}
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Contact Info *
                </label>
                <input
                  type="text"
                  name="contact_info"
                  required
                  placeholder="e.g., reception@acme.com | +90 212 555 0000"
                  value={formData.contact_info}
                  onChange={handleChange}
                  className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Additional Configurations */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Services (Optional)
                  </label>
                  <input
                    type="text"
                    name="services"
                    placeholder="e.g., Haircut, Beard trim"
                    value={formData.services}
                    onChange={handleChange}
                    className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Pricing (Optional)
                  </label>
                  <input
                    type="text"
                    name="pricing"
                    placeholder="e.g., Haircut: 150 TL"
                    value={formData.pricing}
                    onChange={handleChange}
                    className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Subscription Plan
                  </label>
                  <select
                    name="plan"
                    value={formData.plan}
                    onChange={handleChange}
                    className="w-full bg-gray-950 border border-gray-700 text-gray-100 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all cursor-pointer"
                  >
                    <option value="starter">Starter Plan</option>
                    <option value="pro">Pro Plan</option>
                    <option value="enterprise">Enterprise Plan</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Validation Alert */}
          {errorMsg && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div className="text-sm font-medium">
                <span className="font-semibold block">Onboarding Failed</span>
                <span className="opacity-95 mt-1 block">{errorMsg}</span>
              </div>
            </div>
          )}

          {/* Action CTA */}
          <div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:opacity-50 text-white font-bold py-4 rounded-lg shadow-lg hover:shadow-blue-600/10 transition-all flex items-center justify-center gap-2 cursor-pointer text-sm uppercase tracking-wider"
            >
              {loading && <RefreshCw className="w-4 h-4 animate-spin" />}
              {loading ? 'Registering Tenant...' : 'Register Client'}
            </button>
          </div>
        </form>
      ) : (
        /* Success State card view */
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 sm:p-10 shadow-xl text-center space-y-6">
          {result.status === 'pending_verification' ? (
            <div className="w-16 h-16 bg-emerald-500/15 text-emerald-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/30">
              <CheckCircle2 className="w-9 h-9" />
            </div>
          ) : (
            <div className="w-16 h-16 bg-red-500/15 text-red-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/30">
              <AlertCircle className="w-9 h-9" />
            </div>
          )}

          <h2 className="text-2xl font-bold tracking-tight text-white">
            {result.status === 'pending_verification' 
              ? 'Onboarding Successfully Initiated!' 
              : 'Onboarding Failed'}
          </h2>

          <p className="text-gray-400 text-sm max-w-md mx-auto leading-relaxed">
            {result.status === 'pending_verification'
              ? 'The client details have been successfully verified and ingested into the platform. Awaiting WhatsApp Business registration verification.'
              : 'The client registration could not be completed. See error details below.'}
          </p>

          <div className="bg-gray-950 border border-gray-800 rounded-xl p-6 text-left space-y-5 max-w-xl mx-auto font-sans text-sm">
            <div>
              <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">Tenant ID</span>
              <span className="font-mono text-white block select-all break-all">{result.tenant_id}</span>
            </div>

            <div>
              <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">WhatsApp Phone ID</span>
              <span className="font-mono text-blue-400 block break-all">
                {result.phone_number_id || 'Not Registered (Simulation Mode)'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-6 pt-2 border-t border-gray-900">
              <div>
                <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">Knowledge Base</span>
                <span className="text-white font-medium block">{result.knowledge_fields_ingested} fields ingested</span>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-gray-500 block uppercase tracking-wider mb-1">Active Persona</span>
                <span className="text-white font-medium block">{result.persona || 'N/A'}</span>
              </div>
            </div>

            {result.error && (
              <div className="border-t border-gray-900 pt-4">
                <span className="text-[10px] font-semibold text-red-500 block uppercase tracking-wider mb-1">Encountered Error</span>
                <span className="text-red-400 font-medium block leading-relaxed">{result.error}</span>
              </div>
            )}
          </div>

          <div className="pt-6 flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleReset}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-all cursor-pointer text-sm"
            >
              Onboard Another Client
            </button>
            <button
              onClick={() => {
                window.location.hash = `#/dashboard?tenant_id=${result.tenant_id}`;
              }}
              className="bg-gray-800 hover:bg-gray-700 text-white border border-gray-700 font-semibold py-3 px-6 rounded-lg transition-all cursor-pointer text-sm"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
