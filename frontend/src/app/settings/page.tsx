"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { ArrowLeft, ChevronDown, ChevronUp, Save } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

interface AgentInfo {
  key: string;
  name: string;
  label: string;
  description: string;
}

const AGENTS: AgentInfo[] = [
  {
    key: "weaver",
    name: "The Weaver",
    label: "情節編織者",
    description: "負責生成章節草稿",
  },
  {
    key: "chronicler",
    name: "The Chronicler",
    label: "邏輯守護者",
    description: "負責邏輯審查",
  },
  {
    key: "stylist",
    name: "The Stylist",
    label: "風格校正師",
    description: "負責風格審查與修訂",
  },
  {
    key: "extractor",
    name: "The Extractor",
    label: "情報提取官",
    description: "負責提取角色/世界觀",
  },
  {
    key: "foreseer",
    name: "The Foreseer",
    label: "策劃者",
    description: "負責規劃下章",
  },
  {
    key: "profiler",
    name: "The Profiler",
    label: "風格分析師",
    description: "負責分析作品風格",
  },
  {
    key: "editor_analyst",
    name: "The Editor Analyst",
    label: "編輯分析師",
    description: "負責學習偏好",
  },
];

interface AgentConfigState {
  model: string;
  base_url: string;
  api_key: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const { token, ready } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  // Global defaults
  const [globalModel, setGlobalModel] = useState("");
  const [globalBaseUrl, setGlobalBaseUrl] = useState("");
  const [globalApiKey, setGlobalApiKey] = useState("");

  // Agent configs
  const [agentConfigs, setAgentConfigs] = useState<Record<string, AgentConfigState>>({});

  useEffect(() => {
    if (!ready || !token) return;
    fetchSettings();
  }, [ready, token]);

  const fetchSettings = async () => {
    try {
      const data = await api.getLLMSettings();
      if (data.default) {
        setGlobalModel(data.default.model || "");
        setGlobalBaseUrl(data.default.base_url || "");
        setGlobalApiKey(data.default.api_key || "");
      }
      if (data.agents) {
        const configs: Record<string, AgentConfigState> = {};
        Object.entries(data.agents).forEach(([agentName, agentConfig]: [string, any]) => {
          configs[agentName] = {
            model: agentConfig.model || "",
            base_url: agentConfig.base_url || "",
            api_key: agentConfig.api_key || "",
          };
        });
        setAgentConfigs(configs);
      }
    } catch {
      // Settings might not exist yet
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Build agents dict, only including agents with at least one non-empty field
      const agentsDict: Record<string, { model?: string; base_url?: string; api_key?: string }> = {};
      AGENTS.forEach((a) => {
        const cfg = agentConfigs[a.key];
        if (cfg && (cfg.model || cfg.base_url || cfg.api_key)) {
          agentsDict[a.key] = {
            ...(cfg.model ? { model: cfg.model } : {}),
            ...(cfg.base_url ? { base_url: cfg.base_url } : {}),
            ...(cfg.api_key ? { api_key: cfg.api_key } : {}),
          };
        }
      });

      const settings = {
        default: {
          ...(globalModel ? { model: globalModel } : {}),
          ...(globalBaseUrl ? { base_url: globalBaseUrl } : {}),
          ...(globalApiKey ? { api_key: globalApiKey } : {}),
        },
        agents: agentsDict,
      };
      await api.updateLLMSettings(settings);
      toast.success("設定已儲存");
    } catch {
      toast.error("儲存失敗");
    } finally {
      setSaving(false);
    }
  };

  const updateAgentConfig = (agentKey: string, field: string, value: string) => {
    setAgentConfigs((prev) => ({
      ...prev,
      [agentKey]: {
        ...prev[agentKey],
        [field]: value,
      },
    }));
  };

  const isAgentCustomized = (agentKey: string) => {
    const config = agentConfigs[agentKey];
    return config && (config.model || config.base_url || config.api_key);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">載入中...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-4">
          <button
            onClick={() => router.push("/dashboard")}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-lg font-bold text-gray-900">LLM 設定</h1>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Global Default Section */}
        <section className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">全局預設</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
              <input
                type="text"
                value={globalModel}
                onChange={(e) => setGlobalModel(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
                placeholder="e.g., gpt-4o, claude-3.5-sonnet"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
              <input
                type="text"
                value={globalBaseUrl}
                onChange={(e) => setGlobalBaseUrl(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
                placeholder="e.g., https://api.openai.com/v1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              <input
                type="password"
                value={globalApiKey}
                onChange={(e) => setGlobalApiKey(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
                placeholder="sk-..."
              />
            </div>
          </div>
        </section>

        {/* Agent-specific Section */}
        <section className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">各 Agent 獨立設定</h2>
          <div className="space-y-3">
            {AGENTS.map((agent) => (
              <div
                key={agent.key}
                className="bg-white border border-gray-200 rounded-xl overflow-hidden"
              >
                <button
                  onClick={() =>
                    setExpandedAgent(expandedAgent === agent.key ? null : agent.key)
                  }
                  className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="text-left">
                      <span className="font-medium text-gray-900">{agent.name}</span>
                      <span className="text-gray-500 text-sm ml-2">
                        ({agent.label} -- {agent.description})
                      </span>
                    </div>
                    {isAgentCustomized(agent.key) && (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                        已自訂
                      </span>
                    )}
                  </div>
                  {expandedAgent === agent.key ? (
                    <ChevronUp className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  )}
                </button>

                {expandedAgent === agent.key && (
                  <div className="px-5 pb-5 border-t border-gray-100 pt-4 space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Model
                      </label>
                      <input
                        type="text"
                        value={agentConfigs[agent.key]?.model || ""}
                        onChange={(e) => updateAgentConfig(agent.key, "model", e.target.value)}
                        className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
                        placeholder="留空使用全局預設"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Base URL
                      </label>
                      <input
                        type="text"
                        value={agentConfigs[agent.key]?.base_url || ""}
                        onChange={(e) => updateAgentConfig(agent.key, "base_url", e.target.value)}
                        className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
                        placeholder="留空使用全局預設"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        API Key
                      </label>
                      <input
                        type="password"
                        value={agentConfigs[agent.key]?.api_key || ""}
                        onChange={(e) => updateAgentConfig(agent.key, "api_key", e.target.value)}
                        className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400"
                        placeholder="留空使用預設 Key"
                      />
                      <p className="text-xs text-gray-400 mt-1">留空使用預設 Key</p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? "儲存中..." : "儲存設定"}
          </button>
        </div>
      </main>
    </div>
  );
}
