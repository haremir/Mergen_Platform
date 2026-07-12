import { useState } from 'react';
import { submitOnboarding } from '../api';
import type { OnboardingPayload, OnboardingResult } from '../api';
import { 
  Building2, Phone, Clock, MapPin, FileText, 
  Info, Sparkles, CheckCircle2, AlertCircle, RefreshCw 
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
    <div className="max-w-4xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="mb-8 text-center sm:text-left">
        <h1 className="text-3xl font-extrabold text-white flex items-center justify-center sm:justify-start gap-3">
          <Sparkles className="w-8 h-8 text-violet-500 animate-pulse" />
          Desk Client Onboarding
        </h1>
        <p className="text-gray-400 mt-2">
          Onboard a new tenant to the Mergen Platform by defining their front-desk identity and knowledge scope.
        </p>
      </div>

      {!result ? (
        /* Form Card */
        <div className="bg-[#12131a] border border-[#23242f] rounded-2xl p-6 sm:p-8 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-6">
            <h2 className="text-xl font-semibold text-white border-b border-[#23242f] pb-3 mb-4">
              Business Identity
            </h2>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {/* Business Name */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-violet-400" />
                  Business Name *
                </label>
                <input
                  type="text"
                  name="business_name"
                  required
                  placeholder="e.g., Acme Barber Istanbul"
                  value={formData.business_name}
                  onChange={handleChange}
                  className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>

              {/* WhatsApp Phone Number */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <Phone className="w-4 h-4 text-violet-400" />
                  WhatsApp Phone Number *
                </label>
                <input
                  type="text"
                  name="phone_number"
                  required
                  placeholder="e.g., +905551234567"
                  value={formData.phone_number}
                  onChange={handleChange}
                  className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>
            </div>

            <h2 className="text-xl font-semibold text-white border-b border-[#23242f] pb-3 mt-8 mb-4">
              Knowledge Ingestion
            </h2>

            <div className="space-y-6">
              {/* Business Hours */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-violet-400" />
                  Business Hours *
                </label>
                <input
                  type="text"
                  name="business_hours"
                  required
                  placeholder="e.g., Mon-Fri 09:00-19:00, Sat 10:00-17:00"
                  value={formData.business_hours}
                  onChange={handleChange}
                  className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>

              {/* Location */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-violet-400" />
                  Location / Address *
                </label>
                <input
                  type="text"
                  name="location"
                  required
                  placeholder="e.g., Kadikoy Mah. Ataturk Cad. No:12, Kadikoy/Istanbul"
                  value={formData.location}
                  onChange={handleChange}
                  className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>

              {/* Cancellation Policy */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-violet-400" />
                  Cancellation Policy *
                </label>
                <textarea
                  name="cancellation_policy"
                  required
                  rows={2}
                  placeholder="e.g., 24 hours advance notice required for cancellations."
                  value={formData.cancellation_policy}
                  onChange={handleChange}
                  className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors resize-none"
                />
              </div>

              {/* Contact Info */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <Info className="w-4 h-4 text-violet-400" />
                  Contact Info *
                </label>
                <input
                  type="text"
                  name="contact_info"
                  required
                  placeholder="e.g., reception@acme.com | +90 212 555 0000"
                  value={formData.contact_info}
                  onChange={handleChange}
                  className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                />
              </div>

              {/* Services & Pricing & Plan Group */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Services (Optional)
                  </label>
                  <input
                    type="text"
                    name="services"
                    placeholder="e.g., Haircut, Beard trim"
                    value={formData.services}
                    onChange={handleChange}
                    className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Pricing (Optional)
                  </label>
                  <input
                    type="text"
                    name="pricing"
                    placeholder="e.g., Haircut: 150 TL"
                    value={formData.pricing}
                    onChange={handleChange}
                    className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Subscription Plan
                  </label>
                  <select
                    name="plan"
                    value={formData.plan}
                    onChange={handleChange}
                    className="w-full bg-[#181922] border border-[#2b2c3a] rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                  >
                    <option value="starter">Starter Plan</option>
                    <option value="pro">Pro Plan</option>
                    <option value="enterprise">Enterprise Plan</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Error message */}
            {errorMsg && (
              <div className="bg-[#2a1215] border border-[#ef444450] text-[#ef4444] rounded-xl p-4 flex items-start gap-3 mt-6">
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                <span className="text-sm font-medium">{errorMsg}</span>
              </div>
            )}

            {/* Submit Button */}
            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-violet-600 hover:bg-violet-700 disabled:bg-violet-800 disabled:opacity-50 text-white font-semibold py-4 rounded-xl shadow-lg transition-colors flex items-center justify-center gap-2 cursor-pointer"
              >
                {loading && <RefreshCw className="w-5 h-5 animate-spin" />}
                {loading ? 'Onboarding Client...' : 'Register Client'}
              </button>
            </div>
          </form>
        </div>
      ) : (
        /* Result Card */
        <div className="bg-[#12131a] border border-[#23242f] rounded-2xl p-8 shadow-2xl text-center space-y-6">
          {result.status === 'pending_verification' ? (
            <div className="w-16 h-16 bg-emerald-500/10 text-emerald-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-emerald-500/20">
              <CheckCircle2 className="w-10 h-10" />
            </div>
          ) : (
            <div className="w-16 h-16 bg-red-500/10 text-red-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-500/20">
              <AlertCircle className="w-10 h-10" />
            </div>
          )}

          <h2 className="text-2xl font-bold text-white">
            {result.status === 'pending_verification' 
              ? 'Onboarding Successfully Initiated!' 
              : 'Onboarding Failed'}
          </h2>

          <p className="text-gray-400 max-w-md mx-auto">
            {result.status === 'pending_verification'
              ? 'Tenant has been registered, knowledge fields ingested, and WhatsApp client setup triggered.'
              : 'Process stopped due to an error encountered during setup.'}
          </p>

          <div className="bg-[#181922] border border-[#2b2c3a] rounded-xl p-5 text-left space-y-4 max-w-xl mx-auto">
            <div>
              <span className="text-xs font-semibold text-gray-500 block uppercase tracking-wider">Tenant ID</span>
              <span className="text-sm font-mono text-white block select-all break-all">{result.tenant_id}</span>
            </div>

            <div>
              <span className="text-xs font-semibold text-gray-500 block uppercase tracking-wider">WhatsApp Phone ID</span>
              <span className="text-sm font-mono text-emerald-400 block break-all">
                {result.phone_number_id || 'Not generated (Error/Mock mode)'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-xs font-semibold text-gray-500 block uppercase tracking-wider">Knowledge Fields</span>
                <span className="text-sm text-white font-medium block">{result.knowledge_fields_ingested} indexed</span>
              </div>
              <div>
                <span className="text-xs font-semibold text-gray-500 block uppercase tracking-wider">Persona</span>
                <span className="text-sm text-white font-medium block">{result.persona || 'N/A'}</span>
              </div>
            </div>

            {result.error && (
              <div className="border-t border-[#2b2c3a] pt-4">
                <span className="text-xs font-semibold text-red-500 block uppercase tracking-wider">Error Details</span>
                <span className="text-sm text-red-400 block">{result.error}</span>
              </div>
            )}
          </div>

          <div className="pt-4 flex gap-4 justify-center">
            <button
              onClick={handleReset}
              className="bg-violet-600 hover:bg-violet-700 text-white font-semibold px-6 py-3 rounded-xl transition-colors cursor-pointer"
            >
              Onboard Another Client
            </button>
            <button
              onClick={() => {
                // Navigate to dashboard with this tenantId
                window.location.hash = `#/dashboard?tenant_id=${result.tenant_id}`;
              }}
              className="bg-[#181922] hover:bg-[#202230] border border-[#2b2c3a] text-white font-semibold px-6 py-3 rounded-xl transition-colors cursor-pointer"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
