"use client";

import { Star, Users, Globe, FileJson } from "lucide-react";
import type { Project, CharacterCard } from "@/types/project";
import { StyleControlsPanel } from "@/components/project/StyleControlsPanel";

interface SettingsTabProps {
  project: Project;
  onResetPreferences: () => void;
  onUpdateStyleControls: (controls: Record<string, number>) => void;
  showCharJsonView: boolean;
  setShowCharJsonView: (v: boolean) => void;
}

export function SettingsTab({
  project,
  onResetPreferences,
  onUpdateStyleControls,
  showCharJsonView,
  setShowCharJsonView,
}: SettingsTabProps) {
  const preferences = project.writing_preferences;
  // character_cards can be a dict {name: data} or a list [{name, ...}]
  const rawChars = project.character_cards;
  const characters: CharacterCard[] = Array.isArray(rawChars)
    ? rawChars
    : rawChars && typeof rawChars === "object"
      ? Object.entries(rawChars).map(([name, data]) => ({
          name,
          ...(typeof data === "object" && data !== null ? data as Record<string, unknown> : {}),
        }))
      : [];
  const worldSettings = project.world_settings;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <h2 className="text-xl font-bold text-gray-900">作品設定</h2>

      {/* Style Controls */}
      <StyleControlsPanel
        controls={project.style_controls as Record<string, number> | null}
        onUpdate={onUpdateStyleControls}
      />

      {/* Writing Preferences */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Star className="w-5 h-5 text-yellow-500" />
            <h3 className="text-base font-semibold text-gray-900">
              AI 學到的寫作偏好
            </h3>
          </div>
          <button
            onClick={onResetPreferences}
            className="text-sm text-red-600 hover:text-red-700 border border-red-200 px-3 py-1 rounded-md hover:bg-red-50 transition-colors"
          >
            清空重學
          </button>
        </div>
        {preferences && typeof preferences === "object" ? (
          <div className="space-y-3">
            {Object.entries(preferences).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <span className="text-sm text-gray-700">{key}</span>
                <div className="flex items-center gap-1">
                  {typeof value === "number" ? (
                    Array.from({ length: 5 }).map((_, i) => (
                      <Star
                        key={i}
                        className={`w-4 h-4 ${
                          i < (value as number)
                            ? "text-yellow-400 fill-yellow-400"
                            : "text-gray-300"
                        }`}
                      />
                    ))
                  ) : (
                    <span className="text-sm text-gray-600">
                      {String(value)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">
            尚未學習到寫作偏好。完成幾章後，AI 將自動分析您的風格。
          </p>
        )}
      </section>

      {/* Character Cards */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-blue-500" />
            <h3 className="text-base font-semibold text-gray-900">人物卡</h3>
          </div>
          <button
            onClick={() => setShowCharJsonView(!showCharJsonView)}
            className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-800 border border-gray-200 px-3 py-1 rounded-md hover:bg-gray-50 transition-colors"
          >
            <FileJson className="w-4 h-4" />
            {showCharJsonView ? "卡片檢視" : "JSON 檢視"}
          </button>
        </div>

        {showCharJsonView ? (
          <pre className="text-xs text-gray-700 bg-gray-50 p-4 rounded-lg overflow-x-auto font-mono">
            {JSON.stringify(characters, null, 2)}
          </pre>
        ) : characters.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {characters.map((char, idx) => (
              <div
                key={idx}
                className="border border-gray-200 rounded-lg p-4 hover:border-blue-200 transition-colors"
              >
                <h4 className="font-semibold text-gray-900 mb-2">
                  {char.name || "未命名角色"}
                </h4>
                {char.identity && (
                  <p className="text-sm text-gray-600 mb-1">
                    <span className="text-gray-500">身份:</span> {char.identity}
                  </p>
                )}
                {char.abilities && (
                  <p className="text-sm text-gray-600 mb-1">
                    <span className="text-gray-500">能力:</span> {char.abilities}
                  </p>
                )}
                {char.relationships && (
                  <p className="text-sm text-gray-600 mb-1">
                    <span className="text-gray-500">關係:</span>{" "}
                    {char.relationships}
                  </p>
                )}
                {char.description && (
                  <p className="text-sm text-gray-500 mt-2 italic">
                    {char.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">
            尚無人物卡。在建立專案時添加角色設定。
          </p>
        )}
      </section>

      {/* World Settings */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-5 h-5 text-emerald-500" />
          <h3 className="text-base font-semibold text-gray-900">世界設定</h3>
        </div>
        {worldSettings ? (
          <pre className="text-xs text-gray-700 bg-gray-50 p-4 rounded-lg overflow-x-auto font-mono">
            {JSON.stringify(worldSettings, null, 2)}
          </pre>
        ) : (
          <p className="text-sm text-gray-400">
            尚無世界設定。在建立專案時添加世界觀設定。
          </p>
        )}
      </section>
    </div>
  );
}
