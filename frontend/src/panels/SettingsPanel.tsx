import { useState, useEffect } from "react"
import { Settings, Key, AlertCircle, Check, Loader2, Play, Plus, Trash2, Edit3, Save, X, ToggleLeft, ToggleRight } from "lucide-react"
import TelemetryDashboard from "./TelemetryDashboard"
import { ENV } from "../config/env"

interface ProviderInstance {
  id: string
  name: string
  provider_type: "qwen" | "openai" | "gemini" | "anthropic" | "local"
  api_key: string
  base_url: string
  model: string
  priority: number
  is_enabled: boolean
  is_default: boolean
}

export default function SettingsPanel() {
  const [activeTab, setActiveTab] = useState<"agents" | "telemetry">("agents")

  const [instances, setInstances] = useState<ProviderInstance[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; response?: string } | null>(null)
  const [savingDefault, setSavingDefault] = useState<string | null>(null)

  // Edit / Add Form State
  const [editingId, setEditingId] = useState<string | null>(null) // "new" or instance.id
  const [formName, setFormName] = useState("")
  const [formType, setFormType] = useState<"qwen" | "openai" | "gemini" | "anthropic" | "local">("qwen")
  const [formApiKey, setFormApiKey] = useState("")
  const [formBaseUrl, setFormBaseUrl] = useState("")
  const [formModel, setFormModel] = useState("")
  const [formPriority, setFormPriority] = useState(5)
  const [formIsEnabled, setFormIsEnabled] = useState(true)

  const fetchInstances = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${ENV.API_URL}/settings/providers/instances`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setInstances(data)
    } catch (e) {
      console.error(e)
      setError("Failed to fetch AI agent instances from backend.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInstances()
  }, [])

  const handleSetDefault = async (id: string) => {
    setSavingDefault(id)
    try {
      const response = await fetch(`${ENV.API_URL}/settings/providers/default`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: id }),
      })
      if (!response.ok) {
        throw new Error("Failed to change default agent")
      }
      await fetchInstances()
    } catch (e) {
      console.error(e)
      alert("Failed to save provider setting.")
    } finally {
      setSavingDefault(null)
    }
  }

  const handleTestInstance = async (id: string) => {
    setTestingId(id)
    setTestResult(null)
    try {
      const response = await fetch(`${ENV.API_URL}/settings/providers/instances/${id}/test`, {
        method: "POST",
      })
      const data = await response.json()
      setTestResult(data)
    } catch (e) {
      console.error(e)
      setTestResult({
        success: false,
        message: "Failed to connect to test endpoint."
      })
    } finally {
      setTestingId(null)
    }
  }

  const handleOpenAddForm = () => {
    setEditingId("new")
    setFormName("")
    setFormType("qwen")
    setFormApiKey("")
    setFormBaseUrl("")
    setFormModel("qwen-plus")
    setFormPriority(instances.length + 1)
    setFormIsEnabled(true)
  }

  const handleOpenEditForm = (inst: ProviderInstance) => {
    setEditingId(inst.id)
    setFormName(inst.name)
    setFormType(inst.provider_type)
    setFormApiKey(inst.api_key)
    setFormBaseUrl(inst.base_url)
    setFormModel(inst.model)
    setFormPriority(inst.priority)
    setFormIsEnabled(inst.is_enabled)
  }

  const handleCancelForm = () => {
    setEditingId(null)
  }

  const handleSaveForm = async (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      name: formName,
      provider_type: formType,
      api_key: formApiKey,
      base_url: formBaseUrl,
      model: formModel,
      priority: Number(formPriority),
      is_enabled: formIsEnabled
    }

    try {
      let response
      if (editingId === "new") {
        response = await fetch(`${ENV.API_URL}/settings/providers/instances`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      } else {
        response = await fetch(`${ENV.API_URL}/settings/providers/instances/${editingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      }

      if (!response.ok) {
        throw new Error("Failed to save instance configuration")
      }
      
      setEditingId(null)
      await fetchInstances()
    } catch (e) {
      console.error(e)
      alert("Failed to save Agent Instance configuration.")
    }
  }

  const handleDeleteInstance = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this AI Agent Instance?")) return
    try {
      const response = await fetch(`${ENV.API_URL}/settings/providers/instances/${id}`, {
        method: "DELETE",
      })
      if (!response.ok) {
        throw new Error("Failed to delete instance")
      }
      await fetchInstances()
    } catch (e) {
      console.error(e)
      alert("Failed to delete instance.")
    }
  }

  const getProviderTypeBadgeClass = (type: string) => {
    switch (type) {
      case "qwen": return "bg-purple-500/10 text-purple-400 border-purple-500/25 animate-pulse"
      case "openai": return "bg-green-500/10 text-green-400 border-green-500/25"
      case "gemini": return "bg-blue-500/10 text-blue-400 border-blue-500/25"
      case "anthropic": return "bg-amber-500/10 text-amber-400 border-amber-500/25"
      default: return "bg-gray-500/10 text-gray-400 border-gray-500/25"
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#030304] text-gray-300 font-sans overflow-y-auto selection:bg-blue-500/30">
      <div className="border-b border-[#1a1a22] px-6 py-4 flex items-center justify-between bg-[#08080a] shrink-0 sticky top-0 z-10 shadow-sm">
        <div className="flex items-center space-x-3">
          <Settings className="w-5 h-5 text-blue-400" />
          <h2 className="text-base text-gray-100 font-bold tracking-wide">System Configuration</h2>
        </div>
      </div>

      {/* Tabs Selector */}
      <div className="px-6 py-4 border-b border-[#1a1a22] bg-[#08080a]/50 backdrop-blur-sm shrink-0 flex items-center">
        <div className="inline-flex p-1 bg-[#09090C] border border-white/[0.04] rounded-xl shrink-0">
          <button
            onClick={() => setActiveTab("agents")}
            className={`px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-lg transition-all duration-150 border ${
              activeTab === "agents"
                ? "bg-blue-600/10 border-blue-500/25 text-blue-400 shadow-[0_2px_8px_rgba(59,130,246,0.08)]"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            Agent Instances
          </button>
          <button
            onClick={() => setActiveTab("telemetry")}
            className={`px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-lg transition-all duration-150 border ${
              activeTab === "telemetry"
                ? "bg-blue-600/10 border-blue-500/25 text-blue-400 shadow-[0_2px_8px_rgba(59,130,246,0.08)]"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            Observability logs
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6 max-w-5xl mx-auto w-full">
        {activeTab === "agents" ? (
          <div className="border border-white/[0.04] bg-[#0E0E12] p-5 rounded-xl shadow-[0_4px_24px_rgba(0,0,0,0.25)] space-y-4">

            <div className="flex justify-between items-center pb-2 border-b border-white/[0.04]">
              <h3 className="text-xs font-bold text-gray-200 uppercase tracking-widest flex items-center">
                <Key className="w-4 h-4 mr-2 text-yellow-500 animate-pulse" />
                AI LLM Agents Configuration
              </h3>
              {!editingId && (
                <button
                  onClick={handleOpenAddForm}
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 px-3.5 text-xs font-bold text-white transition duration-150 active:scale-95 shadow-[0_4px_12px_rgba(59,130,246,0.25)]"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Agent Instance
                </button>
              )}
            </div>
            
            <p className="text-xs text-gray-400 leading-relaxed font-sans pb-2">
              Configure multiple AI Agent endpoints (e.g. several Qwen, Gemini, or OpenAI API keys). The system automatically falls back to the next agent if one fails, keeping logs and tracking latency. Priorities start from 1 (highest).
            </p>

            {editingId && (
              <form onSubmit={handleSaveForm} className="border border-blue-500/20 bg-blue-500/5 rounded-xl p-5 mb-6 space-y-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <div className="flex justify-between items-center border-b border-blue-500/10 pb-3">
                  <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                    {editingId === "new" ? "Add New AI Agent" : "Edit AI Agent"}
                  </h4>
                  <button type="button" onClick={handleCancelForm} className="text-gray-400 hover:text-gray-200">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Agent Friendly Name</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Qwen Fast Account"
                      value={formName}
                      onChange={(e) => setFormName(e.target.value)}
                      className="w-full bg-[#09090C] border border-white/[0.06] rounded-lg px-3.5 py-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500/40"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Provider Type</label>
                    <select
                      value={formType}
                      onChange={(e) => {
                        const val = e.target.value as any
                        setFormType(val)
                        // pre-populate standard default model
                        if (val === "qwen") setFormModel("qwen-plus")
                        else if (val === "openai") setFormModel("gpt-4o")
                        else if (val === "gemini") setFormModel("gemini-1.5-flash")
                        else if (val === "anthropic") setFormModel("claude-3-5-sonnet-20241022")
                        else if (val === "local") setFormModel("llama3")
                      }}
                      className="w-full bg-[#09090C] border border-white/[0.06] rounded-lg px-3.5 py-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500/40"
                    >
                      <option value="qwen">QWEN (Compatible Mode)</option>
                      <option value="openai">OpenAI</option>
                      <option value="gemini">Google Gemini</option>
                      <option value="anthropic">Anthropic Claude</option>
                      <option value="local">Local LLM (Ollama/LM Studio)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">API Key</label>
                    <input
                      type="password"
                      placeholder={editingId !== "new" ? "••••••••" : "Enter API key or leave blank for .env"}
                      value={formApiKey}
                      onChange={(e) => setFormApiKey(e.target.value)}
                      className="w-full bg-[#09090C] border border-white/[0.06] rounded-lg px-3.5 py-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500/40"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Custom Base URL (Optional)</label>
                    <input
                      type="text"
                      placeholder="https://..."
                      value={formBaseUrl}
                      onChange={(e) => setFormBaseUrl(e.target.value)}
                      className="w-full bg-[#09090C] border border-white/[0.06] rounded-lg px-3.5 py-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500/40"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Model Name</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. qwen-plus"
                      value={formModel}
                      onChange={(e) => setFormModel(e.target.value)}
                      className="w-full bg-[#09090C] border border-white/[0.06] rounded-lg px-3.5 py-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500/40"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">Switch Priority</label>
                      <input
                        type="number"
                        required
                        min="1"
                        value={formPriority}
                        onChange={(e) => setFormPriority(Number(e.target.value))}
                        className="w-full bg-[#09090C] border border-white/[0.06] rounded-lg px-3.5 py-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500/40"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5 font-sans">Status</label>
                      <button
                        type="button"
                        onClick={() => setFormIsEnabled(!formIsEnabled)}
                        className="mt-2 flex items-center text-xs text-gray-300 hover:text-gray-100 font-semibold"
                      >
                        {formIsEnabled ? (
                          <ToggleRight className="w-6 h-6 text-blue-400 mr-2" />
                        ) : (
                          <ToggleLeft className="w-6 h-6 text-gray-500 mr-2" />
                        )}
                        {formIsEnabled ? "Enabled" : "Disabled"}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-2 border-t border-blue-500/10 pt-3">
                  <button
                    type="button"
                    onClick={handleCancelForm}
                    className="inline-flex h-8 items-center rounded-lg border border-white/[0.06] bg-white/[0.02] px-3.5 text-xs font-semibold text-gray-300 hover:bg-white/[0.06] transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 px-3.5 text-xs font-semibold text-white transition active:scale-95 duration-150 shadow-[0_4px_12px_rgba(59,130,246,0.25)]"
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save Config
                  </button>
                </div>
              </form>
            )}

            {loading ? (
              <div className="flex justify-center items-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
              </div>
            ) : error ? (
              <div className="border border-red-500/20 bg-red-500/10 p-4 rounded-xl text-red-200 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 mt-0.5" />
                <span>{error}</span>
              </div>
            ) : (
              <div className="space-y-3">
                {instances.length === 0 ? (
                  <p className="text-xs text-gray-500 py-6 text-center">No AI Agent instances configured. Add one above.</p>
                ) : (
                  instances
                    .sort((a, b) => a.priority - b.priority)
                    .map((inst) => (
                      <div 
                        key={inst.id} 
                        className={`border rounded-xl p-4 bg-[#14141A] transition flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                          inst.is_default ? "border-blue-500/40 shadow-lg shadow-blue-500/5 bg-[#14141E]" : "border-white/[0.03] hover:border-white/[0.08]"
                        } ${!inst.is_enabled ? "opacity-55" : ""}`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center flex-wrap gap-2">
                            <span className="font-bold text-gray-200 text-xs tracking-wide">{inst.name}</span>
                            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase ${getProviderTypeBadgeClass(inst.provider_type)}`}>
                              {inst.provider_type}
                            </span>
                            <span className="inline-flex items-center rounded-full bg-black/35 border border-white/[0.04] px-2 py-0.5 text-[8px] font-bold uppercase tracking-wider text-gray-400 font-mono">
                              Priority {inst.priority}
                            </span>
                            {!inst.is_enabled && (
                              <span className="inline-flex items-center rounded-full bg-red-500/10 border border-red-500/20 px-2 py-0.5 text-[8px] font-bold uppercase tracking-wider text-red-400">
                                Disabled
                              </span>
                            )}
                            {inst.is_default && (
                              <span className="inline-flex items-center rounded-full border border-blue-400/20 bg-blue-500/10 px-2 py-0.5 text-[8px] font-bold uppercase tracking-wider text-blue-300 shadow-[0_0_8px_rgba(59,130,246,0.1)]">
                                Default Agent
                              </span>
                            )}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-gray-500 font-mono">
                            <span>Model: <span className="text-gray-300 font-semibold">{inst.model}</span></span>
                            {inst.base_url && <span className="truncate">URL: <span className="text-gray-400">{inst.base_url}</span></span>}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            onClick={() => handleTestInstance(inst.id)}
                            disabled={testingId !== null || !inst.is_enabled}
                            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.06] px-3 text-xs font-semibold text-gray-300 transition duration-150 disabled:cursor-not-allowed disabled:opacity-40 active:scale-95"
                            title="Test connection"
                          >
                            {testingId === inst.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Play className="w-3.5 h-3.5 text-gray-400 fill-gray-400/20" />
                            )}
                            Test
                          </button>
                          <button
                            onClick={() => handleSetDefault(inst.id)}
                            disabled={inst.is_default || savingDefault !== null || !inst.is_enabled}
                            className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-bold transition duration-150 disabled:cursor-not-allowed disabled:opacity-45 active:scale-95 ${
                              inst.is_default 
                                ? "bg-blue-600/10 text-blue-400 border border-blue-500/30"
                                : "border border-white/[0.06] bg-white/[0.02] text-gray-300 hover:bg-white/[0.06]"
                            }`}
                          >
                            {savingDefault === inst.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : inst.is_default ? (
                              <Check className="w-3.5 h-3.5 text-blue-400" />
                            ) : null}
                            {inst.is_default ? "Default" : "Set Default"}
                          </button>
                          <button
                            onClick={() => handleOpenEditForm(inst)}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.06] text-gray-400 hover:text-gray-200 transition duration-150 active:scale-95"
                            title="Edit agent"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteInstance(inst.id)}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/20 hover:border-red-500/40 text-red-400 hover:bg-red-500/10 transition duration-150 active:scale-95"
                            title="Delete agent"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))
                )}
              </div>
            )}

            {testResult && (
              <div className={`mt-6 border rounded-xl p-4 text-xs font-mono relative select-text shadow-sm ${
                testResult.success ? "border-green-500/25 bg-green-500/5 text-green-300" : "border-red-500/25 bg-red-500/5 text-red-300"
              }`}>
                <button 
                  onClick={() => setTestResult(null)} 
                  className="absolute top-3.5 right-3.5 text-gray-500 hover:text-gray-300 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="font-bold mb-1.5 flex items-center gap-2 text-xs uppercase tracking-wide">
                  {testResult.success ? (
                    <Check className="w-4 h-4 text-green-400" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-red-400" />
                  )}
                  {testResult.message}
                </div>
                {testResult.response && (
                  <div className="mt-3 bg-[#09090C] p-3.5 border border-white/[0.04] rounded-lg text-gray-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                    {testResult.response}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <TelemetryDashboard />
        )}
      </div>
    </div>
  )
}
